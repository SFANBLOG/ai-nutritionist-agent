"""健康报告接口模块"""
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.health_report import HealthReport
from app.models.user import User
from app.schemas.health_report import (
    HealthReportCreate,
    HealthReportResponse,
    HealthReportUpdate,
)
from app.services.document_text import extract_text
from app.services.health_report_parser import HealthReportParser
from app.services.minio_storage import get_storage

router = APIRouter(prefix="/health-reports", tags=["健康报告"])


@router.post("/", response_model=HealthReportResponse, summary="上传并解析体检报告")
@router.post("", response_model=HealthReportResponse, include_in_schema=False)
def create_health_report(
    report_data: HealthReportCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """上传体检报告,自动解析关键健康指标

    支持两种内容来源:
    - report_content:直接粘贴的文本
    - file_key:已上传到对象存储(MinIO/本地)的文件,后端自动抽取文本
    """
    report_content = report_data.report_content
    file_key = report_data.file_key
    file_url = report_data.file_url

    if not report_content and file_key:
        # 从对象存储读取文件并抽取文本
        storage = get_storage()
        try:
            data, _ = storage.get_object(file_key)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="关联的文件不存在,请重新上传")
        try:
            report_content = extract_text(file_key, data)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))

    if not report_content or not report_content.strip():
        raise HTTPException(status_code=400, detail="请提供报告文本内容或上传报告文件")

    parser = HealthReportParser()
    analysis = parser.parse(report_content)

    report = HealthReport(
        user_id=current_user.id,
        report_name=report_data.report_name,
        report_content=report_content,
        file_key=file_key,
        file_url=file_url,
        analysis_result=analysis,
        blood_glucose=analysis.get("blood_glucose"),
        blood_pressure_systolic=analysis.get("blood_pressure_systolic"),
        blood_pressure_diastolic=analysis.get("blood_pressure_diastolic"),
        uric_acid=analysis.get("uric_acid"),
        cholesterol=analysis.get("cholesterol"),
        triglycerides=analysis.get("triglycerides"),
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


@router.get("/", response_model=List[HealthReportResponse], summary="获取健康报告列表")
def get_health_reports(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return (
        db.query(HealthReport)
        .filter(HealthReport.user_id == current_user.id)
        .order_by(HealthReport.created_at.desc())
        .all()
    )


@router.get("/{report_id}", response_model=HealthReportResponse, summary="获取报告详情")
def get_health_report(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    report = (
        db.query(HealthReport)
        .filter(HealthReport.id == report_id, HealthReport.user_id == current_user.id)
        .first()
    )
    if not report:
        raise HTTPException(status_code=404, detail="报告不存在")
    return report


@router.put("/{report_id}", response_model=HealthReportResponse, summary="更新报告分析结果")
def update_health_report(
    report_id: int,
    payload: HealthReportUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    report = (
        db.query(HealthReport)
        .filter(HealthReport.id == report_id, HealthReport.user_id == current_user.id)
        .first()
    )
    if not report:
        raise HTTPException(status_code=404, detail="报告不存在")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(report, field, value)
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


@router.delete("/{report_id}", summary="删除健康报告")
def delete_health_report(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    report = (
        db.query(HealthReport)
        .filter(HealthReport.id == report_id, HealthReport.user_id == current_user.id)
        .first()
    )
    if not report:
        raise HTTPException(status_code=404, detail="报告不存在")
    db.delete(report)
    db.commit()
    return {"message": "删除成功"}
