"""用户接口模块"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user, get_password_hash, require_superuser
from app.models.user import User
from app.schemas.user import UserResponse, UserUpdate

router = APIRouter(prefix="/users", tags=["用户"])


def _with_bmi(user: User) -> dict:
    """附加 BMI 派生指标"""
    data = {c.name: getattr(user, c.name) for c in user.__table__.columns}
    height_m = (user.height or 0) / 100
    data["bmi"] = round(user.weight / (height_m**2), 1) if height_m > 0 and user.weight else None
    return data


@router.get("/me", response_model=UserResponse, summary="获取当前用户信息")
def read_me(current_user: User = Depends(get_current_user)):
    return _with_bmi(current_user)


@router.put("/me", response_model=UserResponse, summary="更新当前用户资料")
def update_me(
    payload: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    data = payload.model_dump(exclude_unset=True)
    password = data.pop("password", None)
    for field, value in data.items():
        setattr(current_user, field, value)
    if password:
        current_user.hashed_password = get_password_hash(password)
    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return _with_bmi(current_user)


@router.get("/{user_id}", response_model=UserResponse, summary="按 ID 查询用户(管理员)")
def read_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_superuser),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    return _with_bmi(user)
