"""安全认证模块(JWT + bcrypt)"""
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.user import User

# 密码加密:直接使用 bcrypt(避免 passlib 与新版 bcrypt 的兼容问题)
try:
    import bcrypt as _bcrypt

    _BCRYPT_ROUNDS = 12

    def _hash(password: str) -> str:
        return _bcrypt.hashpw(
            password.encode("utf-8")[:72], _bcrypt.gensalt(rounds=_BCRYPT_ROUNDS)
        ).decode("utf-8")

    def _verify(password: str, hashed: str) -> bool:
        return _bcrypt.checkpw(password.encode("utf-8")[:72], hashed.encode("utf-8"))

except Exception:  # pragma: no cover - 回退到 passlib
    from passlib.context import CryptContext

    _pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

    def _hash(password: str) -> str:
        return _pwd_context.hash(password[:72])

    def _verify(password: str, hashed: str) -> bool:
        return _pwd_context.verify(password[:72], hashed)


# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_PREFIX}/auth/login")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证明文密码"""
    try:
        return _verify(plain_password, hashed_password)
    except Exception:
        return False


def get_password_hash(password: str) -> str:
    """生成密码哈希"""
    # bcrypt 上限 72 字节,超长密码先截断避免报错
    return _hash(password[:72])


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """创建访问令牌"""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """获取当前登录用户"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无法验证凭据,请重新登录",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str | None = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise credentials_exception
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="账号已被禁用")
    return user


def require_superuser(current_user: User = Depends(get_current_user)) -> User:
    """需要平台管理员权限的接口依赖。"""
    if not current_user.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员权限")
    return current_user
