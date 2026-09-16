"""默认管理员密码重置脚本。

用途:当忘记默认账号密码、或浏览器自动填充了旧凭据导致登录失败时,
用它把 admin 账号的密码恢复成已知值。

用法(任选其一):

  # 在 Docker 容器内执行(推荐)
  docker exec ain-backend python scripts/reset_admin.py

  # 指定新密码
  docker exec ain-backend python scripts/reset_admin.py --password mypass123

  # 在宿主机 backend/ 目录下执行
  python scripts/reset_admin.py

  # 只想看看当前 admin 状态,不改动
  docker exec ain-backend python scripts/reset_admin.py --check

说明:脚本只依赖应用的 ORM 与安全模块,复用 config.py 里解析好的 DATABASE_URL,
因此容器内(MySQL)与裸机(SQLite 回退)都能正常工作。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# 允许以 `python scripts/reset_admin.py` 方式直接运行
BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import settings  # noqa: E402
from app.core.database import SessionLocal  # noqa: E402
from app.core.security import get_password_hash, verify_password  # noqa: E402
from app.models.user import User  # noqa: E402

DEFAULT_USERNAME = "admin"
DEFAULT_PASSWORD = "admin123"


def describe_target() -> str:
    if settings.is_sqlite:
        return "SQLite (回退模式)"
    return settings.DATABASE_URL.split("@")[-1]


def main() -> int:
    parser = argparse.ArgumentParser(description="重置 AI 营养师默认管理员密码")
    parser.add_argument("--username", default=DEFAULT_USERNAME, help="要重置的用户名(默认 admin)")
    parser.add_argument("--password", default=DEFAULT_PASSWORD, help="新密码(默认 admin123)")
    parser.add_argument("--email", default="admin@ainutritionist.com", help="账号不存在时使用的邮箱")
    parser.add_argument("--check", action="store_true", help="只检查状态,不做修改")
    args = parser.parse_args()

    username: str = args.username.strip()

    print(f"[i] 目标数据库: {describe_target()}")

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()

        if user is None:
            if args.check:
                print(f"[!] 用户 '{username}' 不存在。")
                return 1
            user = User(
                username=username,
                email=args.email,
                hashed_password=get_password_hash(args.password),
                full_name="系统管理员",
                is_superuser=True,
            )
            db.add(user)
            db.commit()
            print(f"[✓] 已创建管理员账号: {username} / {args.password}")
            return 0

        state = "已激活" if user.is_active else "已禁用"
        same = verify_password(args.password, user.hashed_password)
        print(f"[i] 用户 '{username}' 存在 (id={user.id}, 状态={state})")
        print(f"[i] 当前密码是否等于 '{args.password}': {'是' if same else '否'}")

        if args.check:
            return 0

        user.hashed_password = get_password_hash(args.password)
        user.is_active = True
        user.is_superuser = True
        db.commit()
        print(f"[✓] 已重置密码: {username} / {args.password}")
        return 0
    except Exception as exc:  # pragma: no cover
        db.rollback()
        print(f"[x] 操作失败: {exc}")
        return 2
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
