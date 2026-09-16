"""食谱接口模块(多日菜单 + HITL 人工确认闸门)"""
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.health_report import HealthReport
from app.models.recipe import Recipe, RecipeStatus, TastePreference
from app.models.user import User
from app.schemas.recipe import (
    RecipeGenerate,
    RecipeResponse,
    ReviewApproveRequest,
    ReviewRevisionRequest,
)
from app.services.menu_service import serialize_recipe

router = APIRouter(prefix="/recipes", tags=["食谱"])


def _get_owned_recipe(recipe_id: int, db: Session, current_user: User) -> Recipe:
    recipe = (
        db.query(Recipe)
        .filter(Recipe.id == recipe_id, Recipe.user_id == current_user.id)
        .first()
    )
    if not recipe:
        raise HTTPException(status_code=404, detail="食谱不存在")
    return recipe


@router.post("/generate", response_model=RecipeResponse, summary="AI 生成多日个性化食谱")
def generate_recipe(
    generate_data: RecipeGenerate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """运行 LangGraph 多 Agent 工作流,生成并落库多日菜单"""
    health_report = (
        db.query(HealthReport)
        .filter(
            HealthReport.id == generate_data.health_report_id,
            HealthReport.user_id == current_user.id,
        )
        .first()
    )
    if not health_report:
        raise HTTPException(status_code=404, detail="健康报告不存在")

    preferences = (
        db.query(TastePreference).filter(TastePreference.user_id == current_user.id).all()
    )

    from app.services.menu_service import generate_and_persist

    try:
        return generate_and_persist(
            db,
            user=current_user,
            health_report=health_report,
            preferences=preferences,
            days=generate_data.days,
            start_date=generate_data.start_date,
            human_gate=settings.HUMAN_REVIEW_GATE,
            period=generate_data.period,
        )
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/", response_model=List[RecipeResponse], summary="获取食谱列表")
def get_recipes(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    recipes = (
        db.query(Recipe)
        .filter(Recipe.user_id == current_user.id)
        .order_by(Recipe.created_at.desc())
        .all()
    )
    return [serialize_recipe(r) for r in recipes]


@router.get("/{recipe_id}", response_model=RecipeResponse, summary="获取食谱详情(含多日菜单)")
def get_recipe(
    recipe_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return serialize_recipe(_get_owned_recipe(recipe_id, db, current_user))


@router.get("/{recipe_id}/menus", summary="获取食谱的多日菜单明细")
def get_recipe_menus(
    recipe_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """返回每日菜单(含餐次与菜品)的完整结构化数据,供前端按天切换渲染"""
    recipe = _get_owned_recipe(recipe_id, db, current_user)
    from app.services.menu_service import serialize_daily_menu

    return [serialize_daily_menu(dm) for dm in recipe.daily_menus]


@router.post("/{recipe_id}/review/approve", response_model=RecipeResponse, summary="HITL:人工批准食谱")
def approve_recipe(
    recipe_id: int,
    payload: ReviewApproveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """人工确认闸门:用户审阅多日菜单后批准,食谱进入生效状态"""
    recipe = _get_owned_recipe(recipe_id, db, current_user)
    if recipe.status == RecipeStatus.ACTIVE:
        return serialize_recipe(recipe)

    recipe.status = RecipeStatus.ACTIVE
    recipe.review_status = "approved"
    recipe.review_decision = payload.decision or "人工确认通过"
    recipe.reviewed_by = current_user.username
    from datetime import datetime

    recipe.reviewed_at = datetime.now()
    db.commit()
    db.refresh(recipe)
    return serialize_recipe(recipe)


@router.post("/{recipe_id}/review/request-revision", response_model=RecipeResponse, summary="HITL:请求修订(人工退回重做)")
def request_revision(
    recipe_id: int,
    payload: ReviewRevisionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """人工请求修订:据意见重做整份方案,重做后再次进入待确认状态

    超过 MAX_REVISION_REQUESTS 上限后,仍允许修订但会在审核意见中标注已多次修订,
    由人工最终把关(避免无限自动重跑)。
    """
    recipe = _get_owned_recipe(recipe_id, db, current_user)
    new_count = (recipe.revision_count or 0) + 1

    health_report = (
        db.query(HealthReport)
        .filter(HealthReport.id == recipe.health_report_id)
        .first()
        if recipe.health_report_id
        else None
    )
    if health_report is None:
        raise HTTPException(status_code=400, detail="原健康报告已不存在,无法基于其修订")

    preferences = (
        db.query(TastePreference).filter(TastePreference.user_id == current_user.id).all()
    )
    notes = [payload.notes.strip()]
    if new_count > settings.MAX_REVISION_REQUESTS:
        notes.append(
            f"（已第 {new_count} 次修订,请人工重点复核关键禁忌与热量是否合理）"
        )

    recipe.status = RecipeStatus.REVISION_REQUESTED
    recipe.review_status = "revision_requested"
    db.commit()

    from app.services.menu_service import generate_and_persist

    try:
        return generate_and_persist(
            db,
            user=current_user,
            health_report=health_report,
            preferences=preferences,
            days=recipe.days or 1,
            start_date=recipe.start_date,
            human_gate=settings.HUMAN_REVIEW_GATE,
            revision_notes=notes,
            recipe=recipe,
            human_notes=payload.notes.strip(),
            revision_count=new_count,
            period=recipe.cycle_type,
        )
    except ValueError as exc:
        recipe.status = RecipeStatus.PENDING_REVIEW
        recipe.review_status = "pending"
        db.commit()
        raise HTTPException(status_code=500, detail=str(exc))


@router.delete("/{recipe_id}", summary="删除食谱")
def delete_recipe(
    recipe_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    recipe = _get_owned_recipe(recipe_id, db, current_user)
    db.delete(recipe)
    db.commit()
    return {"message": "删除成功"}
