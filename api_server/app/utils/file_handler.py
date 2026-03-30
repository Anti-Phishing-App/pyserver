import uuid
import shutil
from pathlib import Path
from fastapi import UploadFile, HTTPException
from PIL import Image, UnidentifiedImageError

from app.config import UPLOAD_DIR, MAX_BYTES, MAX_UPLOAD_MB


def _detect_image_format(path: Path) -> str:
    """이미지 형식 감지"""
    try:
        with Image.open(path) as img:
            fmt = (img.format or "").lower()
            if not fmt:
                raise HTTPException(status_code=400, detail="지원하지 않는 이미지 형식입니다.")
            return "jpg" if fmt == "jpeg" else fmt
    except UnidentifiedImageError:
        raise HTTPException(status_code=400, detail="손상됐거나 이미지가 아닙니다.")


def save_upload_file(upload_file: UploadFile, max_bytes: int = MAX_BYTES) -> str:
    """
    업로드된 파일을 저장하고 파일명 반환

    Args:
        upload_file: FastAPI UploadFile
        max_bytes: 최대 파일 크기

    Returns:
        저장된 파일명
    """
    if not (upload_file.content_type and upload_file.content_type.startswith("image/")):
        raise HTTPException(status_code=400, detail="이미지 파일만 업로드할 수 있습니다.")

    tmp_name = f"{uuid.uuid4().hex}"
    tmp_path = UPLOAD_DIR / tmp_name

    size = 0
    with tmp_path.open("wb") as buffer:
        while True:
            chunk = upload_file.file.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            if size > max_bytes:
                buffer.close()
                tmp_path.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=413,
                    detail=f"파일 용량 제한({MAX_UPLOAD_MB}MB)를 초과했습니다."
                )
            buffer.write(chunk)

    fmt = _detect_image_format(tmp_path)
    final_name = f"{uuid.uuid4().hex}.{fmt}"
    final_path = UPLOAD_DIR / final_name
    shutil.move(str(tmp_path), str(final_path))
    return final_name
