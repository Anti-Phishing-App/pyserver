"""이미지 업로드 API"""
from typing import List
from fastapi import APIRouter, UploadFile, File
from fastapi.responses import JSONResponse

from app.utils.file_handler import save_upload_file

router = APIRouter()


@router.post("/upload-image")
async def upload_image(file: UploadFile = File(...)):
    """단일 이미지 업로드"""
    name = save_upload_file(file)
    return JSONResponse({"filename": name, "url": f"/uploads/{name}"})


@router.post("/upload-images")
async def upload_images(files: List[UploadFile] = File(...)):
    """다중 이미지 업로드"""
    results = []
    for f in files:
        saved = save_upload_file(f)
        results.append({"filename": saved, "url": f"/uploads/{saved}"})
    return JSONResponse({"files": results})
