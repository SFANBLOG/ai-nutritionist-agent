"""文件上传与下载接口(对象存储)

- POST /api/files/upload :上传文件到 MinIO(或本地磁盘),返回 file_key / file_url
- GET  /api/files/{key}  :经鉴权后返回文件字节(适用于 MinIO 与本地两种后端)
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.services.document_text import extract_text_safe
from app.services.minio_storage import get_storage

router = APIRouter(prefix="/files", tags=["文件"])


@router.post("/upload", summary="上传文件(体检报告等)")
async def upload_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """接收上传文件,存入对象存储(MinIO / 本地磁盘),返回可访问的 key 与 url"""
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="空文件")

    storage = get_storage()
    key = storage.gen_key(file.filename or "file")
    content_type = file.content_type or storage._guess_content_type(key)
    storage.put_object(key, data, content_type)

    file_url = f"{router.prefix}/{key}"
    return {
        "file_key": key,
        "file_name": file.filename,
        "file_url": file_url,
        "content_type": content_type,
        "size": len(data),
        "backend": "minio" if storage.available else "local",
    }


@router.get("/{key}", summary="获取文件(经鉴权)")
def get_file(
    key: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """返回文件字节;用于前端预览/下载上传的报告"""
    storage = get_storage()
    try:
        data, content_type = storage.get_object(key)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="文件不存在")
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=f"读取文件失败:{exc}")

    return Response(content=data, media_type=content_type or "application/octet-stream")


@router.get("/{key}/text", summary="获取文件提取文本(用于报告解析)")
def get_file_text(
    key: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """从对象存储文件抽取纯文本(供前端确认或后端解析复用)"""
    storage = get_storage()
    try:
        data, _ = storage.get_object(key)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="文件不存在")
    text = extract_text_safe(key, data)
    if text is None:
        raise HTTPException(status_code=422, detail="该文件类型暂不支持文本提取")
    return {"file_key": key, "text": text}
