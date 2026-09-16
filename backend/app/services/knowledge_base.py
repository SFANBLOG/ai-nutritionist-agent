"""营养知识库服务

优先使用 Milvus 作为向量存储;若运行环境未安装/无法连接 Milvus,
自动降级为进程内向量检索,保证功能可用(检索接口完全一致)。

两种后端对外暴露统一接口:
    add_documents(documents) -> int
    search(query, n_results) -> [{content, metadata, distance}]
    seed_default_knowledge(force) -> int
    count() -> int
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


class KnowledgeBase:
    """营养知识库管理类"""

    def __init__(
        self,
        collection_name: Optional[str] = None,
        auto_seed: bool = True,
    ):
        from app.services.embeddings import get_embedding_model

        self.embedding = get_embedding_model()
        self.dim = self.embedding.dim
        self.collection_name = collection_name or settings.MILVUS_COLLECTION
        self.backend: str = "memory"
        self._milvus = None  # pymilvus Collection 对象
        self._memory_docs: List[Dict[str, Any]] = []

        self._try_init_milvus()
        if auto_seed:
            self.seed_default_knowledge()

    # ------------------------------------------------------------------ 初始化
    def _try_init_milvus(self) -> None:
        if (settings.VECTOR_DB_TYPE or "milvus").lower() != "milvus":
            logger.info("向量库类型配置为 memory,使用进程内检索")
            return
        try:
            import pymilvus  # type: ignore
            from pymilvus import (  # type: ignore
                Collection,
                CollectionSchema,
                DataType,
                FieldSchema,
                utility,
            )
        except Exception as exc:  # pragma: no cover
            logger.warning("pymilvus 不可用,降级为内置向量检索: %s", exc)
            return

        host = settings.MILVUS_HOST
        port = int(settings.MILVUS_PORT)
        retries = int(settings.MILVUS_CONNECT_RETRIES)
        backoff = float(settings.MILVUS_CONNECT_BACKOFF)

        connected = False
        for attempt in range(1, retries + 1):
            try:
                if not pymilvus.connections.has_connection("default"):
                    pymilvus.connections.connect(
                        alias="default",
                        host=host,
                        port=port,
                        timeout=settings.MILVUS_CONNECT_TIMEOUT,
                    )
                connected = True
                break
            except Exception as exc:  # pragma: no cover - 依赖外部服务
                logger.warning(
                    "连接 Milvus(%s:%s)失败(%d/%d): %s",
                    host,
                    port,
                    attempt,
                    retries,
                    exc,
                )
                if attempt < retries:
                    time.sleep(backoff)

        if not connected:
            logger.warning("Milvus 连接失败,降级为内置向量检索")
            return

        try:
            if not utility.has_collection(self.collection_name):
                collection = Collection(name=self.collection_name, schema=self._build_schema())
                collection.create_index(
                    field_name="embedding",
                    index_params={
                        "index_type": "IVF_FLAT",
                        "metric_type": "IP",
                        "params": {"nlist": 128},
                    },
                )
                logger.info("已创建 Milvus 集合 %s(dim=%d)", self.collection_name, self.dim)
            collection = Collection(name=self.collection_name)
            # 旧集合 schema 缺 evidence_level 字段时,丢弃重建以容纳证据等级
            if "evidence_level" not in [f.name for f in collection.schema.fields]:
                if not settings.MILVUS_AUTO_RECREATE_LEGACY_COLLECTION:
                    raise RuntimeError(
                        "Milvus 集合 schema 过旧且已禁止自动删除；"
                        "请执行受控迁移，或仅在非生产环境设置 "
                        "MILVUS_AUTO_RECREATE_LEGACY_COLLECTION=true"
                    )
                logger.warning(
                    "Milvus 集合 %s schema 过旧(缺 evidence_level),重建以容纳证据等级字段",
                    self.collection_name,
                )
                utility.drop_collection(self.collection_name)
                collection = Collection(name=self.collection_name, schema=self._build_schema())
                collection.create_index(
                    field_name="embedding",
                    index_params={
                        "index_type": "IVF_FLAT",
                        "metric_type": "IP",
                        "params": {"nlist": 128},
                    },
                )
            collection.load()
            self._milvus = collection
            self.backend = "milvus"
            logger.info("知识库后端: Milvus(%s:%s)", host, port)
        except Exception as exc:  # pragma: no cover
            logger.warning("Milvus 集合初始化失败,降级为内置检索: %s", exc)
            self.backend = "memory"

    # ------------------------------------------------------------------ 写入
    def _build_schema(self) -> Any:
        """构建 Milvus 集合 schema(含证据等级字段)"""
        # 此方法也会在 _try_init_milvus 的局部导入作用域之外被调用，
        # 因此必须在自身作用域中导入，避免旧 schema 重建时 NameError。
        from pymilvus import CollectionSchema, DataType, FieldSchema  # type: ignore

        return CollectionSchema(
            [
                FieldSchema(name="pk", dtype=DataType.INT64, is_primary=True, auto_id=True),
                FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=4096),
                FieldSchema(name="source", dtype=DataType.VARCHAR, max_length=256),
                FieldSchema(name="category", dtype=DataType.VARCHAR, max_length=128),
                FieldSchema(name="evidence_level", dtype=DataType.VARCHAR, max_length=8),
                FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=self.dim),
            ],
            description="营养学知识库",
        )

    def add_documents(self, documents: List[Dict[str, Any]]) -> int:
        """批量写入知识文档"""
        if not documents:
            return 0
        texts = [d["content"] for d in documents]
        metadatas = [
            {
                "source": d.get("source", ""),
                "category": d.get("category", ""),
                "evidence_level": d.get("evidence_level", ""),
            }
            for d in documents
        ]

        if self.backend == "milvus" and self._milvus is not None:
            try:
                embeddings = self.embedding.encode_documents(texts)
                contents = [t[:4096] for t in texts]
                sources = [(m["source"] or "")[:256] for m in metadatas]
                categories = [(m["category"] or "")[:128] for m in metadatas]
                evidence_levels = [(m["evidence_level"] or "")[:8] for m in metadatas]
                # 字段顺序需与 schema 一致(pk 为 auto_id 不传)
                self._milvus.insert([contents, sources, categories, evidence_levels, embeddings])
                self._milvus.flush()
                return len(documents)
            except Exception as exc:  # pragma: no cover
                logger.warning("Milvus 写入失败,降级为内置检索: %s", exc)
                self.backend = "memory"

        # 内存后端
        embeddings = self.embedding.encode_documents(texts)
        for text, meta, emb in zip(texts, metadatas, embeddings):
            self._memory_docs.append({"content": text, "metadata": meta, "embedding": emb})
        return len(documents)

    # ------------------------------------------------------------------ 检索
    def search(self, query: str, n_results: int = 5) -> List[Dict[str, Any]]:
        """语义检索,返回 [{content, metadata, distance}]"""
        if not query or not query.strip():
            return []

        if self.backend == "milvus" and self._milvus is not None:
            try:
                if self._milvus.num_entities == 0:
                    return []
                query_embedding = self.embedding.encode_queries([query])[0]
                results = self._milvus.search(
                    data=[query_embedding],
                    anns_field="embedding",
                    param={"metric_type": "IP", "params": {"nprobe": 16}},
                    limit=n_results,
                    output_fields=["content", "source", "category", "evidence_level"],
                )
                documents: List[Dict[str, Any]] = []
                for hit in results[0]:
                    entity = hit.entity
                    documents.append(
                        {
                            "content": entity.get("content"),
                            "metadata": {
                                "source": entity.get("source", ""),
                                "category": entity.get("category", ""),
                                "evidence_level": entity.get("evidence_level", ""),
                            },
                            "distance": hit.distance,
                        }
                    )
                return documents
            except Exception as exc:  # pragma: no cover
                logger.warning("Milvus 检索失败,降级为内置检索: %s", exc)

        # 内存后端:余弦相似度
        from app.services.embeddings import cosine_similarity

        query_embedding = self.embedding.encode_queries([query])[0]
        scored = [
            (
                cosine_similarity(query_embedding, d["embedding"]),
                {"content": d["content"], "metadata": d["metadata"]},
            )
            for d in self._memory_docs
        ]
        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            {
                "content": item[1]["content"],
                "metadata": item[1]["metadata"],
                "distance": round(1 - item[0], 4),
            }
            for item in scored[:n_results]
        ]

    # ------------------------------------------------------------------ 种子数据
    def seed_default_knowledge(self, force: bool = False) -> int:
        """写入默认营养学知识(幂等)"""
        from knowledge_base.default_data import DEFAULT_KNOWLEDGE

        if self.backend == "milvus" and self._milvus is not None:
            try:
                if self._milvus.num_entities > 0 and not force:
                    return 0
            except Exception:  # pragma: no cover
                pass
        elif self._memory_docs and not force:
            return 0
        return self.add_documents(DEFAULT_KNOWLEDGE)

    def count(self) -> int:
        if self.backend == "milvus" and self._milvus is not None:
            try:
                return self._milvus.num_entities
            except Exception:  # pragma: no cover
                return len(self._memory_docs)
        return len(self._memory_docs)


_kb_singleton: Optional[KnowledgeBase] = None


def get_knowledge_base() -> KnowledgeBase:
    """获取知识库单例"""
    global _kb_singleton
    if _kb_singleton is None:
        _kb_singleton = KnowledgeBase()
    return _kb_singleton
