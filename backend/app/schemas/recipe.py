"""食谱 / 菜单 / 餐次 / 菜品 相关 Pydantic 模式"""
from datetime import date, datetime
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.recipe import RecipeStatus


# ---------------- 口味偏好 ----------------
class TastePreferenceCreate(BaseModel):
    """新增口味偏好"""

    preference_type: str = Field(
        ...,
        description="偏好类型: favorite_food / disliked_food / cuisine / allergy / goal",
    )
    preference_value: str = Field(..., max_length=200, description="偏好值")


class TastePreferenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    preference_type: str
    preference_value: str
    created_at: Optional[datetime] = None


# ---------------- 菜品 / 餐次 / 每日菜单 ----------------
class DishResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: Optional[str] = None
    ingredients: Optional[str] = None
    cooking_method: Optional[str] = None
    calories: int = 0
    protein: float = 0
    carbohydrate: float = 0
    fat: float = 0
    fiber: float = 0
    tips: Optional[str] = None


class MealResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    meal_type: str
    target_calories: int = 0
    actual_calories: int = 0
    dishes: List[DishResponse] = []


class DailyMenuResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    recipe_id: int
    menu_date: date
    total_calories: int = 0
    total_protein: float = 0
    total_carbohydrate: float = 0
    total_fat: float = 0
    notes: Optional[str] = None
    meals: List[MealResponse] = []


# ---------------- 食谱 ----------------
class RecipeGenerate(BaseModel):
    """AI 生成食谱(多日)请求"""

    health_report_id: int = Field(..., description="关联的健康报告 ID")
    period: Optional[str] = Field(
        None,
        description="周期类型: week(一周/7天) | month(一个月/30天) | custom(自定义)。"
        "与 days 二选一,period 优先;period=custom 或未提供时使用 days。",
    )
    days: int = Field(7, ge=1, le=90, description="自定义天数(1~90);period 非 custom 时被忽略")
    start_date: Optional[date] = Field(None, description="方案起始日期,默认今天")


class RecipeCreate(BaseModel):
    """手动创建食谱"""

    name: str = Field(..., max_length=200)
    description: Optional[str] = None
    nutrition_info: Optional[dict[str, Any]] = None
    total_calories: int = 0
    health_report_id: Optional[int] = None
    status: RecipeStatus = RecipeStatus.ACTIVE


class RecipeResponse(BaseModel):
    """食谱响应(含嵌套的多日菜单)"""

    id: int
    user_id: int
    health_report_id: Optional[int] = None
    name: str
    description: Optional[str] = None
    nutrition_info: Optional[dict[str, Any]] = None
    total_calories: int = 0
    status: Optional[RecipeStatus] = None
    # 多日菜单
    days: int = 1
    start_date: Optional[date] = None
    cycle_type: Optional[str] = None
    cycle_label: Optional[str] = None
    # HITL 审核闸门
    review_status: Optional[str] = "pending"
    review_decision: Optional[str] = None
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    revision_count: int = 0
    human_notes: Optional[str] = None
    # 嵌套菜单
    menus: List[DailyMenuResponse] = []
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ---------------- HITL 审核闸门 ----------------
class ReviewApproveRequest(BaseModel):
    """人工批准食谱"""

    decision: Optional[str] = Field(None, description="确认意见(可选)")


class ReviewRevisionRequest(BaseModel):
    """人工请求修订"""

    notes: str = Field(..., min_length=1, max_length=1000, description="修订意见,将作为重做指令")
