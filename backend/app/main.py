"""FastAPI 主应用"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api import auth, files, health_reports, preferences, recipes, users
from app.core.config import settings
from app.core.database import Base, engine
from app.core.observability import RequestContextMiddleware
from app.core.security import get_password_hash
from app.models.user import User

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
logger = logging.getLogger("ai-nutritionist")


def init_database() -> None:
    """创建数据表并初始化默认管理员"""
    # 导入模型以注册元数据
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    from app.core.database import migrate_schema

    migrate_schema()

    from app.core.database import SessionLocal

    db = SessionLocal()
    try:
        if not db.query(User).filter(User.username == "admin").first():
            db.add(
                User(
                    username="admin",
                    email="admin@ainutritionist.com",
                    hashed_password=get_password_hash("admin123"),
                    full_name="系统管理员",
                    is_superuser=True,
                )
            )
            db.commit()
            logger.info("已创建默认管理员账号: admin / admin123")
    except Exception as exc:  # pragma: no cover
        db.rollback()
        logger.warning("初始化管理员失败: %s", exc)
    finally:
        db.close()


def init_knowledge_base() -> None:
    """初始化营养知识库(写入默认知识)"""
    try:
        from app.services.knowledge_base import get_knowledge_base

        kb = get_knowledge_base()
        added = kb.seed_default_knowledge()
        logger.info("知识库就绪: 后端=%s, 文档数=%s, 本次新增=%s", kb.backend, kb.count(), added)
    except Exception as exc:  # pragma: no cover
        logger.warning("知识库初始化失败(不影响主流程): %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期:启动时初始化数据库与知识库"""
    configuration_errors = settings.production_configuration_errors()
    if configuration_errors:
        raise RuntimeError("生产配置校验失败: " + "；".join(configuration_errors))
    init_database()
    init_knowledge_base()
    logger.info(
        "%s v%s 启动完成 | LLM=%s | 数据库=%s",
        settings.APP_NAME,
        settings.APP_VERSION,
        settings.LLM_MODEL if settings.llm_configured else "未配置(规则引擎模式)",
        "SQLite" if settings.is_sqlite else settings.DATABASE_URL.split("://")[0],
    )
    yield
    logger.info("%s 已关闭", settings.APP_NAME)


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="AI 营养师 Agent —— 基于 LangGraph 多 Agent 协作的智能个性化营养饮食管理系统",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestContextMiddleware)

# 注册路由
PREFIX = settings.API_PREFIX
app.include_router(auth.router, prefix=PREFIX)
app.include_router(users.router, prefix=PREFIX)
app.include_router(health_reports.router, prefix=PREFIX)
app.include_router(recipes.router, prefix=PREFIX)
app.include_router(preferences.router, prefix=PREFIX)
app.include_router(files.router, prefix=PREFIX)


@app.get("/", tags=["系统"], summary="根路径")
def root():
    return {
        "message": "欢迎使用 AI 营养师 Agent",
        "version": settings.APP_VERSION,
        "docs": "/docs",
    }


@app.get("/health", tags=["系统"], summary="健康检查")
@app.get(f"{PREFIX}/health", tags=["系统"], summary="健康检查(带 API 前缀)", include_in_schema=False)
def health_check():
    from app.services.knowledge_base import get_knowledge_base
    from app.services.minio_storage import get_storage

    kb = get_knowledge_base()
    storage = get_storage()
    return {
        "status": "healthy",
        "llm_configured": settings.llm_configured,
        "embedding_provider": settings.embedding_provider,
        "embedding_dim": kb.dim,
        "knowledge_backend": kb.backend,
        "knowledge_docs": kb.count(),
        "object_storage": "minio" if storage.available else "local",
        "vector_db_type": settings.VECTOR_DB_TYPE,
        "human_review_gate": settings.HUMAN_REVIEW_GATE,
        "menu_max_days": settings.MENU_MAX_DAYS,
    }


@app.get("/ready", tags=["系统"], summary="就绪检查")
def readiness_check():
    """供编排平台使用：只验证接收流量所必需的数据库连接。"""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception as exc:
        logger.warning("就绪检查失败: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="数据库暂不可用",
        ) from exc
    return {"status": "ready", "environment": settings.ENVIRONMENT}


if __name__ == "__main__":
    # 直接运行入口:python -m app.main / python app/main.py
    # 必须读取平台注入的 PORT 并绑定 0.0.0.0(绑定 127.0.0.1 会导致容器网络无法访问)
    import os

    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "8000")),
        log_level="info",
    )
