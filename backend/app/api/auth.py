"""认证接口模块"""
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import create_access_token, get_password_hash, verify_password
from app.models.user import User
from app.schemas.user import Token, UserCreate, UserResponse
from app.services.audit import record_audit_event

router = APIRouter(prefix="/auth", tags=["认证"])


@router.post("/register", response_model=UserResponse, summary="用户注册")
def register(user_data: UserCreate, request: Request, db: Session = Depends(get_db)):
    """用户注册"""
    username = (user_data.username or "").strip()
    email = (user_data.email or "").strip()

    if db.query(User).filter(User.username == username).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="用户名已存在")

    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="邮箱已被注册")

    payload = user_data.model_dump(exclude={"password"})
    payload["username"] = username
    payload["email"] = email
    user = User(**payload, hashed_password=get_password_hash(user_data.password))
    db.add(user)
    db.flush()
    record_audit_event(
        db,
        action="user.registered",
        resource_type="user",
        actor_user_id=user.id,
        resource_id=user.id,
        request_id=getattr(request.state, "request_id", None),
    )
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=Token, summary="用户登录")
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    request: Request = None,
    db: Session = Depends(get_db),
):
    """用户登录(OAuth2 密码模式,表单提交)

    注意:浏览器自动填充可能在用户名/密码前后带入空白字符,这里统一做去空白处理,
    避免出现「明明输对了却提示用户名或密码错误」的误导性 401。
    """
    username = (form_data.username or "").strip()
    password = (form_data.password or "").strip()

    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="账号已被禁用")

    record_audit_event(
        db,
        action="auth.login_succeeded",
        resource_type="user",
        actor_user_id=user.id,
        resource_id=user.id,
        request_id=getattr(request.state, "request_id", None) if request else None,
    )
    db.commit()
    access_token = create_access_token(
        data={"sub": user.username},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return {"access_token": access_token, "token_type": "bearer"}
