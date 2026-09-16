"""多日菜单编排与持久化服务

把 LangGraph 工作流按天展开:
  - 第 1 天执行完整四 Agent 流程(健康分析→营养规划→食谱生成→质量审核)
  - 后续天数复用同一份指标,仅做「按天轮换」的食谱生成,保证相邻天不重复
最终把结构化结果落库到 recipes / daily_menus / meals / dishes 三张关联表,
并按 HUMAN_REVIEW_GATE 决定食谱进入「待人工确认」还是直接生效。
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Any, List, Optional

from sqlalchemy.orm import Session

from app.agents.workflow import NutritionAgentWorkflow, _orm_to_profile
from app.core.config import settings
from app.models.recipe import (
    Dish,
    DailyMenu,
    Meal,
    Recipe,
    RecipeStatus,
)


def _cycle_label(period: str, days: int) -> str:
    """把周期类型映射为可读标签(用于卡片/详情展示)"""
    if period == "week":
        return "一周"
    if period == "month":
        return "一个月"
    return f"自定义 {days} 天"


def generate_and_persist(
    db: Session,
    *,
    user: Any,
    health_report: Any,
    preferences: List[Any],
    days: int,
    start_date: Optional[date] = None,
    human_gate: bool = True,
    extra_instruction: Optional[str] = None,
    revision_notes: Optional[List[str]] = None,
    recipe: Optional[Recipe] = None,
    human_notes: Optional[str] = None,
    revision_count: Optional[int] = None,
    period: Optional[str] = None,
) -> dict:
    """运行多日工作流并落库,返回序列化后的食谱(dict)

    recipe 非空表示「修订重做」:清空旧菜单后重写,沿用同一食谱主键。
    period: week(一周/7天) | month(一个月/30天) | custom(自定义,用 days)。
    """
    # 周期类型 -> 天数(week/month 覆盖入参 days;custom 沿用 days)
    period = (period or "custom")
    if period == "week":
        days = settings.MENU_PERIOD_WEEK_DAYS
    elif period == "month":
        days = settings.MENU_PERIOD_MONTH_DAYS
    days = max(1, min(settings.MENU_MAX_DAYS, int(days)))
    if start_date is None:
        start_date = date.today()
    elif isinstance(start_date, str):
        start_date = date.fromisoformat(start_date)

    profile = _orm_to_profile(user)
    workflow = NutritionAgentWorkflow(human_gate=human_gate)
    target = workflow.generator.estimate_target_calories(profile)

    days_data: List[dict] = []
    first_result: Optional[dict] = None
    for d in range(days):
        if d == 0 and revision_notes:
            instr = "（人工修订意见,请据此调整整份方案）" + "；".join(revision_notes)
            if extra_instruction:
                instr += "\n" + extra_instruction
        elif d == 0:
            instr = extra_instruction
        else:
            instr = (
                f"这是方案第 {d + 1} 天,请与前面天数轮换主菜与食材,避免连续两天重复;"
                f"保持每日总热量约 {target} kcal,并符合用户健康状况与忌口。"
            )
        res = workflow.run(
            health_report=health_report,
            preferences=preferences,
            user_info=user,
            day_index=d,
            extra_instruction=instr,
        )
        day_recipe = res.get("recipe") or {}
        if not day_recipe.get("meals"):
            continue
        day_recipe.setdefault("tips", [])
        day_recipe["review"] = res.get("review_result", {})
        days_data.append({"result": res, "recipe": day_recipe})
        if first_result is None:
            first_result = res

    if not days_data:
        raise ValueError("AI 未能生成任何有效菜单,请稍后重试")

    # ---- 构建 / 复用食谱主记录 ----
    if recipe is None:
        recipe = Recipe(
            user_id=user.id,
            health_report_id=getattr(health_report, "id", None),
        )
        db.add(recipe)

    total_all = sum(d["recipe"].get("total_calories", 0) for d in days_data)
    first = days_data[0]["result"]

    # 先赋值所有必填字段,再 flush,避免 NOT NULL 约束在清空旧菜单时提前插入空行
    recipe.name = days_data[0]["recipe"].get("name") or "个性化营养食谱"
    recipe.description = days_data[0]["recipe"].get("description", "")
    recipe.days = days
    recipe.start_date = start_date
    recipe.cycle_type = period
    recipe.cycle_label = _cycle_label(period, days)
    recipe.total_calories = total_all
    recipe.nutrition_info = {
        "health_analysis": first.get("health_analysis", ""),
        "nutrition_plan": first.get("nutrition_plan", ""),
        "knowledge_refs": first.get("knowledge_snippets") or [],
        "review": first.get("review_result", {}),
        "agent_log": first.get("log", []),
        "llm_enabled": first.get("llm_enabled", False),
        "days": days,
        "per_day_calories": [d["recipe"].get("total_calories", 0) for d in days_data],
    }

    # HITL 闸门状态
    if human_gate:
        recipe.status = RecipeStatus.PENDING_REVIEW
        recipe.review_status = "pending"
    else:
        recipe.status = RecipeStatus.ACTIVE
        passed = (first.get("review_result", {}) or {}).get("passed", False)
        recipe.review_status = "approved" if passed else "pending"

    if human_notes is not None:
        recipe.human_notes = human_notes
    if revision_count is not None:
        recipe.revision_count = revision_count

    # 清空旧的多日菜单(修订重做时)。仅在已存在(已有 id)的食谱上执行,
    # 新建食谱关系本就为空,提前 flush 会触发 name 空值插入。
    if recipe.id is not None:
        recipe.daily_menus = []
    db.flush()

    # ---- 落库每日菜单 / 餐次 / 菜品 ----
    for d, entry in enumerate(days_data):
        dr = entry["recipe"]
        ni = dr.get("nutrition_info") or {}
        dm = DailyMenu(
            recipe_id=recipe.id,
            user_id=user.id,
            menu_date=start_date + timedelta(days=d),
        )
        dm.total_calories = dr.get("total_calories", 0)
        dm.total_protein = ni.get("protein", 0)
        dm.total_carbohydrate = ni.get("carbs", 0)
        dm.total_fat = ni.get("fat", 0)
        dm.notes = json.dumps(
            {"tips": dr.get("tips", []), "day_review": dr.get("review", {})},
            ensure_ascii=False,
        )
        db.add(dm)
        db.flush()

        for m in dr.get("meals", []):
            meal = Meal(
                menu_id=dm.id,
                meal_type=m.get("meal_type"),
                target_calories=m.get("target_calories", 0),
                actual_calories=m.get("actual_calories", 0),
            )
            db.add(meal)
            db.flush()
            for dish in m.get("dishes", []):
                db.add(
                    Dish(
                        meal_id=meal.id,
                        name=dish.get("name", ""),
                        description=dish.get("description"),
                        ingredients=dish.get("ingredients"),
                        cooking_method=dish.get("cooking_method"),
                        calories=dish.get("calories", 0),
                        protein=dish.get("protein", 0),
                        carbohydrate=dish.get("carbohydrate", 0),
                        fat=dish.get("fat", 0),
                        fiber=dish.get("fiber", 0),
                        tips=dish.get("tips"),
                    )
                )

    db.commit()
    db.refresh(recipe)
    return serialize_recipe(recipe)


# --------------------------------------------------------------------------
# 序列化(在数据库 session 内调用,避免懒加载脱离会话)
# --------------------------------------------------------------------------
def serialize_recipe(recipe: Recipe) -> dict:
    return {
        "id": recipe.id,
        "user_id": recipe.user_id,
        "health_report_id": recipe.health_report_id,
        "name": recipe.name,
        "description": recipe.description,
        "nutrition_info": recipe.nutrition_info,
        "total_calories": recipe.total_calories,
        "status": recipe.status,
        "days": recipe.days,
        "start_date": recipe.start_date,
        "cycle_type": recipe.cycle_type,
        "cycle_label": recipe.cycle_label,
        "review_status": recipe.review_status,
        "review_decision": recipe.review_decision,
        "reviewed_by": recipe.reviewed_by,
        "reviewed_at": recipe.reviewed_at,
        "revision_count": recipe.revision_count,
        "human_notes": recipe.human_notes,
        "menus": [serialize_daily_menu(dm) for dm in recipe.daily_menus],
        "created_at": recipe.created_at,
        "updated_at": recipe.updated_at,
    }


def serialize_daily_menu(dm: DailyMenu) -> dict:
    return {
        "id": dm.id,
        "recipe_id": dm.recipe_id,
        "menu_date": dm.menu_date,
        "total_calories": dm.total_calories,
        "total_protein": dm.total_protein,
        "total_carbohydrate": dm.total_carbohydrate,
        "total_fat": dm.total_fat,
        "notes": dm.notes,
        "meals": [
            {
                "id": m.id,
                "meal_type": m.meal_type,
                "target_calories": m.target_calories,
                "actual_calories": m.actual_calories,
                "dishes": [
                    {
                        "id": d.id,
                        "name": d.name,
                        "description": d.description,
                        "ingredients": d.ingredients,
                        "cooking_method": d.cooking_method,
                        "calories": d.calories,
                        "protein": d.protein,
                        "carbohydrate": d.carbohydrate,
                        "fat": d.fat,
                        "fiber": d.fiber,
                        "tips": d.tips,
                    }
                    for d in m.dishes
                ],
            }
            for m in dm.meals
        ],
    }
