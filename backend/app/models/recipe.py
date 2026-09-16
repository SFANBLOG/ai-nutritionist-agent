"""食谱 / 菜单 / 餐次 / 菜品 数据模型"""
import enum

from sqlalchemy import (
    JSON,
    Column,
    Date,
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class RecipeStatus(str, enum.Enum):
    """食谱状态枚举

    - DRAFT:            草稿(尚未生成完成)
    - PENDING_REVIEW:   已生成,等待人工确认(HITL 闸门开启时)
    - ACTIVE:           已生效/已批准
    - REVISION_REQUESTED: 用户请求修订,正在重做(瞬时态)
    - ARCHIVED:         已归档
    """

    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    ACTIVE = "active"
    REVISION_REQUESTED = "revision_requested"
    ARCHIVED = "archived"


class MealType(str, enum.Enum):
    """餐次类型枚举"""

    BREAKFAST = "breakfast"
    LUNCH = "lunch"
    DINNER = "dinner"
    SNACK = "snack"


def _enum(enum_cls):
    """统一使用 VARCHAR + CHECK 存储枚举,兼容 SQLite / MySQL"""
    return SAEnum(enum_cls, native_enum=False, values_callable=lambda e: [m.value for m in e])


class TastePreference(Base):
    """口味偏好表模型"""

    __tablename__ = "taste_preferences"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    # 类型: favorite_food / disliked_food / cuisine / allergy / goal
    preference_type = Column(String(50), nullable=False, comment="偏好类型")
    preference_value = Column(String(200), nullable=False, comment="偏好值")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", backref="taste_preferences")


class Recipe(Base):
    """食谱表模型(一份食谱 = 一个多日膳食方案计划)"""

    __tablename__ = "recipes"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    health_report_id = Column(Integer, ForeignKey("health_reports.id", ondelete="SET NULL"))
    name = Column(String(200), nullable=False, comment="食谱名称")
    description = Column(Text, comment="食谱描述")
    nutrition_info = Column(JSON, comment="营养信息(健康分析/营养方案/审核结果/Agent日志等摘要)")
    total_calories = Column(Integer, default=0, comment="多日累计总热量(kcal)")
    status = Column(_enum(RecipeStatus), default=RecipeStatus.ACTIVE, comment="状态")
    # 多日菜单
    days = Column(Integer, default=1, comment="方案覆盖天数")
    start_date = Column(Date, comment="方案起始日期")
    # 周期类型: week(一周) / month(一个月) / custom(自定义) —— 前端选择器映射
    cycle_type = Column(String(20), default="custom", comment="周期类型: week/month/custom")
    cycle_label = Column(String(40), comment="周期标签,如 一周/一个月/自定义 N 天")
    # 质量审核人工确认闸门(HITL)
    review_status = Column(String(20), default="pending", comment="审核闸门状态: pending/approved/revision_requested")
    review_decision = Column(Text, comment="人工确认意见/结论")
    reviewed_by = Column(String(50), comment="确认人(用户名)")
    reviewed_at = Column(DateTime(timezone=True), comment="确认时间")
    revision_count = Column(Integer, default=0, comment="人工请求修订次数")
    human_notes = Column(Text, comment="最近一次人工修订意见")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user = relationship("User", backref="recipes")
    health_report = relationship("HealthReport", backref="recipes")
    daily_menus = relationship(
        "DailyMenu",
        back_populates="recipe",
        cascade="all, delete-orphan",
        order_by="DailyMenu.menu_date",
    )


class DailyMenu(Base):
    """每日菜单表模型(隶属于某个食谱计划,一天一条)"""

    __tablename__ = "daily_menus"

    id = Column(Integer, primary_key=True, index=True)
    recipe_id = Column(Integer, ForeignKey("recipes.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    menu_date = Column(Date, nullable=False)
    total_calories = Column(Integer, default=0)
    total_protein = Column(Float, default=0)
    total_carbohydrate = Column(Float, default=0)
    total_fat = Column(Float, default=0)
    notes = Column(Text, comment="当日备注/饮食建议(JSON 或文本)")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", backref="daily_menus")
    recipe = relationship("Recipe", back_populates="daily_menus")
    meals = relationship(
        "Meal",
        back_populates="menu",
        cascade="all, delete-orphan",
        order_by="Meal.id",
    )


class Meal(Base):
    """餐次表模型"""

    __tablename__ = "meals"

    id = Column(Integer, primary_key=True, index=True)
    menu_id = Column(Integer, ForeignKey("daily_menus.id", ondelete="CASCADE"), nullable=False)
    meal_type = Column(_enum(MealType), nullable=False)
    target_calories = Column(Integer, default=0)
    actual_calories = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    menu = relationship("DailyMenu", back_populates="meals")
    dishes = relationship(
        "Dish",
        back_populates="meal",
        cascade="all, delete-orphan",
        order_by="Dish.id",
    )


class Dish(Base):
    """菜品表模型"""

    __tablename__ = "dishes"

    id = Column(Integer, primary_key=True, index=True)
    meal_id = Column(Integer, ForeignKey("meals.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(200), nullable=False)
    description = Column(Text)
    ingredients = Column(Text, comment="食材清单")
    cooking_method = Column(Text, comment="烹饪方法")
    calories = Column(Integer, default=0)
    protein = Column(Float, default=0)
    carbohydrate = Column(Float, default=0)
    fat = Column(Float, default=0)
    fiber = Column(Float, default=0)
    tips = Column(Text, comment="健康提示")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    meal = relationship("Meal", back_populates="dishes")
