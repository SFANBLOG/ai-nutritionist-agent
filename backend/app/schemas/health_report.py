"""健康报告相关 Pydantic 模式"""
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class HealthReportBase(BaseModel):
    report_name: str = Field(..., max_length=200, description="报告名称")
    report_content: Optional[str] = Field(None, description="报告原始文本内容(与 file_key 二选一)")


class HealthReportCreate(HealthReportBase):
    """创建(上传)健康报告

    两种方式二选一:
    1. 直接提供 report_content(文本粘贴)
    2. 提供 file_key(已通过 /api/files/upload 上传到对象存储的文件)
    """

    file_key: Optional[str] = Field(None, description="对象存储中的文件 key(与 file_url 配套)")
    file_url: Optional[str] = Field(None, description="文件可访问地址")


class HealthReportUpdate(BaseModel):
    analysis_result: Optional[dict[str, Any]] = None
    blood_glucose: Optional[float] = None
    blood_pressure_systolic: Optional[int] = None
    blood_pressure_diastolic: Optional[int] = None
    uric_acid: Optional[float] = None
    cholesterol: Optional[float] = None
    triglycerides: Optional[float] = None


class HealthReportResponse(BaseModel):
    """健康报告响应"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    report_name: str
    report_content: Optional[str] = None
    file_key: Optional[str] = None
    file_url: Optional[str] = None
    analysis_result: Optional[dict[str, Any]] = None
    blood_glucose: Optional[float] = None
    blood_pressure_systolic: Optional[int] = None
    blood_pressure_diastolic: Optional[int] = None
    uric_acid: Optional[float] = None
    cholesterol: Optional[float] = None
    triglycerides: Optional[float] = None
    created_at: Optional[datetime] = None
