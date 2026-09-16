"""健康报告数据模型"""
from sqlalchemy import JSON, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class HealthReport(Base):
    """健康报告表模型"""

    __tablename__ = "health_reports"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    report_name = Column(String(200), nullable=False, comment="报告名称")
    report_content = Column(Text, comment="报告原始内容")
    file_key = Column(String(255), comment="对象存储文件 key")
    file_url = Column(String(512), comment="对象存储文件访问地址")
    analysis_result = Column(JSON, comment="AI 分析结果")
    blood_glucose = Column(Float, comment="血糖(mmol/L)")
    blood_pressure_systolic = Column(Integer, comment="收缩压(mmHg)")
    blood_pressure_diastolic = Column(Integer, comment="舒张压(mmHg)")
    uric_acid = Column(Float, comment="尿酸(μmol/L)")
    cholesterol = Column(Float, comment="胆固醇(mmol/L)")
    triglycerides = Column(Float, comment="甘油三酯(mmol/L)")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # 关系
    user = relationship("User", backref="health_reports")
