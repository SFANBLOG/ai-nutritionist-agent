"""应用配置模块"""
import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/ 目录
BASE_DIR = Path(__file__).resolve().parents[2]


def _pb_data_dir() -> str:
    """托管平台(如 PocketBay)注入的持久卷目录,未注入时为空串"""
    return (os.environ.get("POCKETBAY_DATA_DIR") or "").strip()


# 运行时数据目录:
#   平台注入 POCKETBAY_DATA_DIR(如 /data 持久卷)时用它,保证跨更新不丢数据;
#   否则沿用 backend/data(本地与 Docker 行为不变)。
DATA_DIR = Path(_pb_data_dir()) if _pb_data_dir() else (BASE_DIR / "data")


def _default_database_url() -> str:
    """默认数据库连接串。

    平台注入 POCKETBAY_DATA_DIR 时 => 使用落在持久卷上的 SQLite,
    避免依赖外部 MySQL/PostgreSQL;未注入时 => 保持 MySQL 默认(开箱即用)。
    始终可通过显式设置 DATABASE_URL 覆盖。
    """
    if _pb_data_dir():
        return f"sqlite:///{DATA_DIR.as_posix()}/ai_nutritionist.db"
    return (
        "mysql+pymysql://ai_user:ai_password@localhost:3306/ai_nutritionist?charset=utf8mb4"
    )


class Settings(BaseSettings):
    """应用配置类"""

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # ---------- 应用 ----------
    APP_NAME: str = "AI 营养师 Agent"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    ENVIRONMENT: str = "development"  # development / staging / production
    LOG_LEVEL: str = "INFO"
    API_PREFIX: str = "/api"
    REQUEST_ID_HEADER: str = "X-Request-ID"

    # ---------- 数据库 ----------
    # 默认使用 MySQL(开箱即用,与 docker-compose 中 mysql 服务凭据一致)。
    # 本地裸机运行若无 MySQL,start.py 会自动探测并在不可达时回退 SQLite。
    # 托管平台(注入 POCKETBAY_DATA_DIR)时自动改用持久卷上的 SQLite。
    # 切换/覆盖示例:
    #   用 SQLite:  DATABASE_URL=sqlite:///./data/ai_nutritionist.db
    #   自定义 MySQL: DATABASE_URL=mysql+pymysql://root:password@localhost:3306/ai_nutritionist?charset=utf8mb4
    DATABASE_URL: str = _default_database_url()

    # ---------- JWT ----------
    SECRET_KEY: str = "your-secret-key-here-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24

    # ---------- LLM(兼容 OpenAI 协议:OpenAI / DeepSeek / 通义千问等) ----------
    OPENAI_API_KEY: str = "sk-your-openai-api-key"
    OPENAI_BASE_URL: str = "https://api.deepseek.com/v1"
    LLM_MODEL: str = "deepseek-chat"
    LLM_TEMPERATURE: float = 0.7
    LLM_TIMEOUT: int = 120

    # ---------- Embedding(BGE 本地向量化,默认) ----------
    # 默认使用 BGE 中文向量模型(BAAI/bge-small-zh-v1.5,512 维),零外部 API、可离线。
    # 常见可选:
    #   BAAI/bge-base-zh-v1.5   (768 维,效果更好)
    #   BAAI/bge-large-zh-v1.5  (1024 维,效果最好、最重)
    # 切换大模型时务必同步修改 EMBEDDING_DIM 与之一致。
    # 仍可使用 OpenAI 兼容 embedding:填写 OPENAI_EMBEDDING_MODEL(此时优先于 BGE)。
    EMBEDDING_MODEL: str = "BAAI/bge-small-zh-v1.5"
    EMBEDDING_DIM: int = 512
    OPENAI_EMBEDDING_MODEL: str = ""
    # 向量化后端选择:auto | bge | openai | hash
    #   auto   = 本地/Docker 优先 BGE;托管平台(容器内存与构建预算有限)自动降级为哈希,
    #            避免启动时加载 torch/BGE 导致启动超时或 OOM
    #   bge    = 强制本地 BGE    openai = 强制 OpenAI 兼容    hash = 强制零依赖哈希
    EMBEDDING_BACKEND: str = "auto"

    # ---------- 向量库(Milvus) ----------
    # 可选值: milvus | memory
    # memory = 进程内向量检索(无需外部服务,适合本地轻量开发)
    VECTOR_DB_TYPE: str = "milvus"
    MILVUS_HOST: str = "localhost"
    MILVUS_PORT: int = 19530
    MILVUS_COLLECTION: str = "nutrition_knowledge"
    MILVUS_CONNECT_TIMEOUT: int = 10
    MILVUS_CONNECT_RETRIES: int = 12
    MILVUS_CONNECT_BACKOFF: float = 5.0
    # 旧 schema 的集合可能包含人工维护知识；生产环境禁止自动删除重建。
    MILVUS_AUTO_RECREATE_LEGACY_COLLECTION: bool = False

    # ---------- 对象存储(MinIO) ----------
    # 留空 => 使用本地磁盘 data/uploads 兜底(无需外部服务)
    # Docker 部署示例: MINIO_ENDPOINT=minio:9000
    MINIO_ENDPOINT: str = ""
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET: str = "ai-nutritionist-uploads"
    MINIO_SECURE: bool = False

    # ---------- CORS ----------
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:8080,http://localhost:18080,http://localhost:3000,http://127.0.0.1:5173"

    # ---------- Agent 工作流 ----------
    MAX_REVIEW_ITERATIONS: int = 3

    # ---------- 质量审核人工确认闸门(HITL) ----------
    # True  => 食谱生成后进入「待人工确认」状态,需用户在前端点「批准」才生效;
    #          用户也可「请求修订」,后端据意见重做并再次进入待确认(防死循环由人工控制)。
    # False => 沿用旧行为:审核不通过自动回退食谱生成 Agent 重做,最多 3 轮。
    HUMAN_REVIEW_GATE: bool = True
    # 人工请求修订的最大次数(超出后再次请求仅追加记录,不再自动重跑,由人工兜底)
    MAX_REVISION_REQUESTS: int = 3

    # ---------- 多日菜单 ----------
    MENU_DEFAULT_DAYS: int = 1
    MENU_MAX_DAYS: int = 90
    # 周期类型 -> 天数映射(前端「一周 / 一个月 / 自定义」)
    MENU_PERIOD_WEEK_DAYS: int = 7
    MENU_PERIOD_MONTH_DAYS: int = 30

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def is_sqlite(self) -> bool:
        return self.DATABASE_URL.startswith("sqlite")

    @property
    def managed_platform(self) -> bool:
        """是否运行在托管平台容器里(注入了持久卷变量 POCKETBAY_DATA_DIR)"""
        return bool(_pb_data_dir())

    @property
    def llm_configured(self) -> bool:
        """是否配置了真实可用的 LLM Key"""
        key = (self.OPENAI_API_KEY or "").strip()
        return bool(key) and not key.startswith("sk-your") and "your-" not in key

    @property
    def embedding_provider(self) -> str:
        """当前生效的 embedding 提供方:bge / openai / hash"""
        from app.services.embeddings import get_embedding_model

        return get_embedding_model().mode

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() == "production"

    def production_configuration_errors(self) -> list[str]:
        """返回生产环境不可接受的配置项，供启动时阻断部署。"""
        if not self.is_production:
            return []
        errors: list[str] = []
        unsafe_secrets = {
            "your-secret-key-here-change-in-production",
            "change-me-in-production-please",
            "",
        }
        if self.SECRET_KEY in unsafe_secrets or len(self.SECRET_KEY) < 32:
            errors.append("SECRET_KEY 必须使用至少 32 字符的随机值")
        if self.DEBUG:
            errors.append("生产环境必须设置 DEBUG=false")
        if "*" in self.cors_origin_list:
            errors.append("生产环境禁止 CORS_ORIGINS 包含通配符")
        if self.DATABASE_URL.startswith("sqlite"):
            errors.append("生产环境必须使用受管 MySQL 或 PostgreSQL，而非 SQLite")
        return errors


settings = Settings()

DATA_DIR.mkdir(parents=True, exist_ok=True)
