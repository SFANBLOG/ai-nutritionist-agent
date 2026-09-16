"""从上传文件中抽取纯文本

支持:
- .txt / .md :直接按 UTF-8 解码(失败回退 GBK)
- .pdf       :若安装了 pypdf,抽取全部页面文本;否则抛出明确错误
其他类型统一抛出不支持错误。
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Union

logger = logging.getLogger(__name__)

SUPPORTED_SUFFIXES = {".txt", ".md", ".pdf"}


def extract_text(filename: str, data: bytes) -> str:
    """从文件字节中抽取文本,失败抛出 ValueError"""
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise ValueError(
            f"不支持的文件类型:{suffix or '未知'},目前仅支持 .txt / .md / .pdf"
        )

    if suffix in (".txt", ".md"):
        for enc in ("utf-8", "gbk", "latin-1"):
            try:
                return data.decode(enc)
            except (UnicodeDecodeError, LookupError):
                continue
        raise ValueError("文本文件解码失败,请确认编码为 UTF-8 或 GBK")

    # .pdf
    try:
        import pypdf  # type: ignore
    except Exception:
        raise ValueError("解析 PDF 需要后端安装 pypdf,请改用 .txt 粘贴,或安装依赖后重试")

    try:
        from io import BytesIO

        reader = pypdf.PdfReader(BytesIO(data))
        parts = []
        for page in reader.pages:
            try:
                parts.append(page.extract_text() or "")
            except Exception as exc:  # pragma: no cover
                logger.warning("PDF 单页解析失败: %s", exc)
        return "\n".join(parts).strip()
    except Exception as exc:
        raise ValueError(f"PDF 解析失败:{exc}")


def extract_text_safe(filename: str, data: bytes) -> Union[str, None]:
    """安全抽取;失败返回 None(用于非文本场景,如图片仅存储不解析)"""
    try:
        return extract_text(filename, data)
    except Exception as exc:  # pragma: no cover
        logger.info("文件 %s 文本抽取跳过:%s", filename, exc)
        return None
