"""口味偏好接口模块"""
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.recipe import TastePreference
from app.models.user import User
from app.schemas.recipe import TastePreferenceCreate, TastePreferenceResponse

router = APIRouter(prefix="/preferences", tags=["口味偏好"])

VALID_TYPES = {"favorite_food", "disliked_food", "cuisine", "allergy", "goal"}


@router.get("/", response_model=List[TastePreferenceResponse], summary="获取口味偏好列表")
def list_preferences(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return (
        db.query(TastePreference)
        .filter(TastePreference.user_id == current_user.id)
        .order_by(TastePreference.created_at.desc())
        .all()
    )


@router.post("/", response_model=TastePreferenceResponse, summary="新增口味偏好")
def create_preference(
    payload: TastePreferenceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if payload.preference_type not in VALID_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"preference_type 必须为 {sorted(VALID_TYPES)} 之一",
        )
    exists = (
        db.query(TastePreference)
        .filter(
            TastePreference.user_id == current_user.id,
            TastePreference.preference_type == payload.preference_type,
            TastePreference.preference_value == payload.preference_value,
        )
        .first()
    )
    if exists:
        raise HTTPException(status_code=400, detail="该偏好已存在")

    pref = TastePreference(
        user_id=current_user.id,
        preference_type=payload.preference_type,
        preference_value=payload.preference_value,
    )
    db.add(pref)
    db.commit()
    db.refresh(pref)
    return pref


@router.delete("/{preference_id}", summary="删除口味偏好")
def delete_preference(
    preference_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    pref = (
        db.query(TastePreference)
        .filter(
            TastePreference.id == preference_id,
            TastePreference.user_id == current_user.id,
        )
        .first()
    )
    if not pref:
        raise HTTPException(status_code=404, detail="偏好不存在")
    db.delete(pref)
    db.commit()
    return {"message": "删除成功"}
