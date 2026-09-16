"""API 路由聚合"""
from app.api import auth, health_reports, preferences, recipes, users

__all__ = ["auth", "users", "health_reports", "recipes", "preferences"]
