"""文本向量化(BGE 本地模型,默认)

设计目标:
- 默认使用 BGE 中文向量模型(BAAI/bge-small-zh-v1.5),本地推理、零外部 API、可离线。
- 支持可选 OpenAI 兼容 embedding(填写 OPENAI_EMBEDDING_MODEL 时优先)。
- 若 sentence-transformers 未安装或模型加载失败,自动降级为哈希向量(保证可用)。
- BGE 检索场景下,查询需加指令前缀(文档不加),已在 encode_queries 中处理。
"""
from __future__ import annotations

import logging
import math
import hashlib
import re
from typing import Iterable, List, Optional, Sequence

logger = logging.getLogger(__name__)

# BGE 官方推荐的检索查询前缀(仅对 query 使用,document 不加)
BGE_QUERY_PREFIX = "为这个句子生成表示以用于检索相关文章:"

_TOKEN_RE = re.compile(r"[a-zA-Z0-9]+|[\u4e00-\u9fff]")


def _hash_embed(text: str, dim: int) -> List[float]:
    """基于字符 n-gram 哈希的本地兜底向量化(对中文语料稳定)"""
    vec = [0.0] * dim
    text = text or ""
    base = _TOKEN_RE.findall(text)
    grams: List[str] = list(base)
    cjk = [t for t in base if len(t) == 1 and "\u4e00" <= t <= "\u9fff"]
    for n in (2, 3):
        for i in range(len(cjk) - n + 1):
            grams.append("".join(cjk[i : i + n]))
    words = [t.lower() for t in base if len(t) > 1]
    for i in range(len(words) - 1):
        grams.append(words[i] + "_" + words[i + 1])
    if not grams:
        return vec
    for g in grams:
        h = hashlib.md5(g.encode("utf-8")).digest()
        for k in (0, 4):
            idx = int.from_bytes(h[k : k + 4], "little") % dim
            sign = 1.0 if h[k + 4] % 2 == 0 else -1.0
            vec[idx] += sign
    norm = math.sqrt(sum(v * v for v in vec))
    if norm > 0:
        vec = [v / norm for v in vec]
    return vec


def _normalize(vecs: Sequence[Sequence[float]]) -> List[List[float]]:
    out: List[List[float]] = []
    for v in vecs:
        arr = list(v)
        norm = math.sqrt(sum(x * x for x in arr))
        out.append([x / norm for x in arr] if norm > 0 else arr)
    return out


class OpenAIEmbeddingFunction:
    """OpenAI 协议 embedding 封装(惰性导入 openai SDK)"""

    def __init__(self, api_key: str, base_url: str, model: str):
        from openai import OpenAI

        self._client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model

    def __call__(self, input: Sequence[str]) -> List[List[float]]:  # noqa: A002
        resp = self._client.embeddings.create(model=self.model, input=list(input))
        return [d.embedding for d in resp.data]


class EmbeddingModel:
    """统一的向量化入口

    优先级:bge 本地模型 > openai 兼容 > 哈希兜底。
    """

    def __init__(self) -> None:
        from app.core.config import settings

        self.dim: int = int(settings.EMBEDDING_DIM)
        self.model_name: str = settings.EMBEDDING_MODEL
        self.mode: str = "hash"  # bge | openai | hash

        self._bge = None
        self._openai = None

        raw = (getattr(settings, "EMBEDDING_BACKEND", "auto") or "auto").strip().lower()
        if raw not in ("auto", "bge", "openai", "hash"):
            raw = "auto"
        # auto:托管平台跳过重型本地模型(哈希零依赖、启动秒级);本地/Docker 仍优先 BGE
        resolved = ("hash" if settings.managed_platform else "bge") if raw == "auto" else raw

        # 1) OpenAI 兼容 embedding(显式指定;或未禁用本地模型且已配置时优先 —— 保持既有优先序)
        want_openai = resolved == "openai" or (
            resolved == "bge" and bool((settings.OPENAI_EMBEDDING_MODEL or "").strip())
        )
        if want_openai and settings.llm_configured:
            try:
                self._openai = OpenAIEmbeddingFunction(
                    api_key=settings.OPENAI_API_KEY,
                    base_url=settings.OPENAI_BASE_URL,
                    model=settings.OPENAI_EMBEDDING_MODEL,
                )
                self.mode = "openai"
                logger.info("Embedding 提供方: OpenAI(%s)", settings.OPENAI_EMBEDDING_MODEL)
            except Exception as exc:  # pragma: no cover
                logger.warning("OpenAI embedding 初始化失败,尝试 BGE: %s", exc)

        # 2) BGE 本地模型(仅在未被 disabled 时加载)
        if resolved in ("bge", "openai") and self.mode == "hash":
            try:
                from sentence_transformers import SentenceTransformer

                logger.info("正在加载 BGE 向量模型: %s", self.model_name)
                self._bge = SentenceTransformer(self.model_name)
                real_dim = self._bge.get_sentence_embedding_dimension()
                if real_dim:
                    self.dim = int(real_dim)
                self.mode = "bge"
                logger.info("Embedding 提供方: BGE(%s, %d 维)", self.model_name, self.dim)
            except Exception as exc:  # pragma: no cover - 环境相关
                logger.warning("BGE 模型不可用,降级为哈希向量: %s", exc)

        if self.mode == "hash":
            reason = "托管平台环境,已跳过本地 BGE" if (raw == "auto" and resolved == "hash") else "兜底"
            logger.info("Embedding 提供方: 哈希(%d 维,零外部依赖) [%s]", self.dim, reason)

    # ------------------------------------------------------------------ 编码
    def encode_documents(self, texts: Iterable[str]) -> List[List[float]]:
        texts = [t or "" for t in texts]
        if not texts:
            return []
        if self.mode == "bge":
            return _normalize(self._bge.encode(texts, normalize_embeddings=True, batch_size=32))
        if self.mode == "openai":
            return self._openai(list(texts))
        return [_hash_embed(t, self.dim) for t in texts]

    def encode_queries(self, texts: Iterable[str]) -> List[List[float]]:
        texts = [t or "" for t in texts]
        if not texts:
            return []
        if self.mode == "bge":
            prefixed = [BGE_QUERY_PREFIX + t for t in texts]
            return _normalize(self._bge.encode(prefixed, normalize_embeddings=True, batch_size=32))
        if self.mode == "openai":
            return self._openai(list(texts))
        return [_hash_embed(t, self.dim) for t in texts]


_model_singleton: Optional[EmbeddingModel] = None


def get_embedding_model() -> EmbeddingModel:
    """获取向量化单例(惰性加载)"""
    global _model_singleton
    if _model_singleton is None:
        _model_singleton = EmbeddingModel()
    return _model_singleton


# 向后兼容的模块级函数
def embed_texts(texts: Iterable[str]) -> List[List[float]]:
    return get_embedding_model().encode_documents(list(texts))


def embed_text(text: str) -> List[float]:
    return get_embedding_model().encode_documents([text])[0]


def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    """余弦相似度(输入无需已归一化)"""
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)
