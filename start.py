#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""AI 营养师 Agent 一键启动脚本

用法:
    python start.py                  # 同时启动后端与前端
    python start.py --backend-only   # 只启动后端
    python start.py --frontend-only  # 只启动前端
"""
from __future__ import annotations

import argparse
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"

BACKEND_PORT = 8000
FRONTEND_PORT = 5173

# 默认使用 MySQL(与 docker-compose 中 mysql 服务凭据一致);
# 裸机运行若探测不到 MySQL,会自动回退到 SQLite,保证开箱即用。
MYSQL_URL = "mysql+pymysql://ai_user:ai_password@localhost:3306/ai_nutritionist?charset=utf8mb4"
SQLITE_PATH = BACKEND / "data" / "ai_nutritionist.db"
SQLITE_URL = f"sqlite:///{SQLITE_PATH.as_posix()}"

processes: list[subprocess.Popen] = []


def log(msg: str) -> None:
    print(f"[启动器] {msg}", flush=True)


def _mysql_reachable(timeout: float = 3.0) -> bool:
    """探测本地 MySQL(默认凭据)是否可连接"""
    try:
        import pymysql  # 依赖 requirements.txt 中的 pymysql
    except Exception:  # pragma: no cover
        return False
    try:
        conn = pymysql.connect(
            host="localhost",
            port=3306,
            user="ai_user",
            password="ai_password",
            database="ai_nutritionist",
            connect_timeout=timeout,
        )
        conn.close()
        return True
    except Exception:  # pragma: no cover
        return False


def resolve_database_url() -> str:
    """解析实际使用的 DATABASE_URL:

    - 用户已通过环境变量设置 -> 直接采用;
    - 否则探测 MySQL,可达则用 MySQL(默认),不可达则回退 SQLite 并打印提示。
    """
    env_url = os.environ.get("DATABASE_URL")
    if env_url:
        return env_url
    if _mysql_reachable():
        log("检测到本地 MySQL,使用 MySQL 作为数据库")
        return MYSQL_URL
    log("未检测到可用的 MySQL,自动回退到 SQLite(数据文件: %s)", SQLITE_PATH)
    return SQLITE_URL


def check_backend_deps() -> bool:
    try:
        import fastapi  # noqa: F401
        import sqlalchemy  # noqa: F401
        import langgraph  # noqa: F401
    except ImportError as exc:
        log(f"后端依赖缺失: {exc}")
        log("请先执行: cd backend && pip install -r requirements.txt")
        return False
    return True


def start_backend() -> subprocess.Popen | None:
    if not check_backend_deps():
        return None

    env = os.environ.copy()
    env["PYTHONPATH"] = str(BACKEND) + os.pathsep + env.get("PYTHONPATH", "")
    env.setdefault("PYTHONUNBUFFERED", "1")
    # 解析数据库(MySQL 优先,不可达则回退 SQLite),注入后端进程
    env["DATABASE_URL"] = resolve_database_url()

    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "app.main:app",
        "--reload",
        "--host",
        "0.0.0.0",
        "--port",
        str(BACKEND_PORT),
    ]
    log(f"启动后端: http://localhost:{BACKEND_PORT}  (API 文档 /docs)")
    return subprocess.Popen(cmd, cwd=str(BACKEND), env=env)


def start_frontend() -> subprocess.Popen | None:
    if not (FRONTEND / "package.json").exists():
        log("未找到 frontend/package.json")
        return None

    if not (FRONTEND / "node_modules").exists():
        log("检测到未安装前端依赖,正在执行 npm install …")
        npm = shutil.which("npm") or "npm"
        subprocess.run([npm, "install"], cwd=str(FRONTEND), shell=(os.name == "nt"))

    npm = shutil.which("npm") or "npm"
    log(f"启动前端: http://localhost:{FRONTEND_PORT}")
    return subprocess.Popen(
        [npm, "run", "dev"], cwd=str(FRONTEND), shell=(os.name == "nt")
    )


def shutdown(*_args) -> None:
    log("正在关闭服务 …")
    for proc in processes:
        if proc and proc.poll() is None:
            try:
                proc.terminate()
            except Exception:  # pragma: no cover
                pass
    time.sleep(1)
    for proc in processes:
        if proc and proc.poll() is None:
            try:
                proc.kill()
            except Exception:  # pragma: no cover
                pass
    sys.exit(0)


def main() -> None:
    parser = argparse.ArgumentParser(description="AI 营养师 Agent 一键启动")
    parser.add_argument("--backend-only", action="store_true", help="仅启动后端")
    parser.add_argument("--frontend-only", action="store_true", help="仅启动前端")
    args = parser.parse_args()

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    print("=" * 56)
    print("  🍎 AI 营养师 Agent  ——  LangGraph 多 Agent 协作")
    print("=" * 56)

    if not args.frontend_only:
        proc = start_backend()
        if proc:
            processes.append(proc)
            time.sleep(3)

    if not args.backend_only:
        proc = start_frontend()
        if proc:
            processes.append(proc)

    if not processes:
        log("没有可启动的服务,请检查依赖安装情况")
        sys.exit(1)

    print("-" * 56)
    print(f"  后端: http://localhost:{BACKEND_PORT}/docs")
    print(f"  前端: http://localhost:{FRONTEND_PORT}")
    print(f"  账号: admin / admin123")
    print("-" * 56)
    print("  按 Ctrl+C 停止所有服务")
    print("=" * 56)

    while True:
        time.sleep(1)
        for proc in list(processes):
            if proc.poll() is not None:
                log(f"进程已退出(returncode={proc.returncode})")
                processes.remove(proc)
        if not processes:
            log("所有服务已退出")
            break


if __name__ == "__main__":
    main()
