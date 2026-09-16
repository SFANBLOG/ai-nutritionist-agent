"""数据库连接模块"""
import logging
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import settings

logger = logging.getLogger(__name__)

_engine_kwargs: dict = {"pool_pre_ping": True, "future": True}

if settings.is_sqlite:
    # SQLite:允许跨线程使用(FastAPI 线程池),并确保数据目录存在
    db_path = Path(settings.DATABASE_URL.split("///", 1)[-1])
    db_path.parent.mkdir(parents=True, exist_ok=True)
    _engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    # MySQL / PostgreSQL 等关系型数据库
    _engine_kwargs.update(pool_size=10, max_overflow=20, pool_recycle=3600)

# 创建数据库引擎
engine = create_engine(settings.DATABASE_URL, **_engine_kwargs)

# 创建会话工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 创建基类
Base = declarative_base()


def get_db():
    """获取数据库会话(依赖注入)"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def migrate_schema() -> None:
    """轻量自迁移:为已存在的表补齐新增列(兼容老库,无需外部迁移工具)

    仅在列确实缺失时才发起 ALTER,避免重复执行报错;兼容 SQLite / MySQL。
    """
    from sqlalchemy import inspect

    inspector = inspect(engine)
    if not inspector.has_table("recipes"):
        return

    existing = {c["name"] for c in inspector.get_columns("recipes")}
    desired = {
        "cycle_type": "VARCHAR(20)",
        "cycle_label": "VARCHAR(40)",
    }
    for col, ddl_type in desired.items():
        if col in existing:
            continue
        try:
            with engine.begin() as conn:
                # SQLAlchemy 2.0 要求用 text() 包裹 DDL 字符串(SQLite / MySQL 均支持该语法)
                conn.execute(
                    text(f"ALTER TABLE recipes ADD COLUMN {col} {ddl_type}")
                )
            logger.info("迁移: recipes 已新增列 %s", col)
        except Exception as exc:  # pragma: no cover
            logger.warning("迁移: 新增列 %s 失败(可忽略): %s", col, exc)
