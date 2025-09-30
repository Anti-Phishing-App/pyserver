import os
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from typing import List
from pathlib import Path
import uuid, shutil

from PIL import Image, UnidentifiedImageError  

app = FastAPI()

# 업로드 디렉터리
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")

# 환경변수로 업로드 한도 조절 (기본 100MB)
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "100"))
MAX_BYTES = MAX_UPLOAD_MB * 1024 * 1024

@app.get("/")
def read_root():
    return {"Hello": "World"}

def _detect_image_format(path: Path) -> str:
    """
    Pillow로 이미지 포맷 판별. (jpeg, png, webp, gif 등 소문자 반환)
    유효하지 않으면 예외 발생.
    """
    try:
        with Image.open(path) as img:
            fmt = (img.format or "").lower()
            if not fmt:
                raise HTTPException(status_code=400, detail="지원하지 않는 이미지 형식입니다.")
            return "jpg" if fmt == "jpeg" else fmt
    except UnidentifiedImageError:
        raise HTTPException(status_code=400, detail="손상됐거나 이미지가 아닙니다.")

def _save_uploadfile(upload_file: UploadFile, max_bytes: int = MAX_BYTES) -> str:
    if not (upload_file.content_type and upload_file.content_type.startswith("image/")):
        raise HTTPException(status_code=400, detail="이미지 파일만 업로드할 수 있습니다.")

    tmp_name = f"{uuid.uuid4().hex}"
    tmp_path = UPLOAD_DIR / tmp_name

    size = 0
    with tmp_path.open("wb") as buffer:
        while True:
            chunk = upload_file.file.read(1024 * 1024)  # 1MB씩 스트리밍
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

    # 이미지 유효성/포맷 판별 (Pillow)
    fmt = _detect_image_format(tmp_path)

    final_name = f"{uuid.uuid4().hex}.{fmt}"
    final_path = UPLOAD_DIR / final_name
    shutil.move(str(tmp_path), str(final_path))
    return final_name

@app.post("/upload-image")
async def upload_image(file: UploadFile = File(...)):
    name = _save_uploadfile(file)
    return JSONResponse({"filename": name, "url": f"/uploads/{name}"})

@app.post("/upload-images")
async def upload_images(files: List[UploadFile] = File(...)):
    results = []
    for f in files:
        saved = _save_uploadfile(f)
        results.append({"filename": saved, "url": f"/uploads/{saved}"})
    return JSONResponse({"files": results})
