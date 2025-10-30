# ocr_run.py

import requests
import uuid
import time
import json
import os

# 이 파일에서 발생하는 오류를 명확히 하기 위한 커스텀 예외 클래스
class OCRError(Exception):
    pass

API_URL = os.getenv("CLOVA_API_URL")
SECRET_KEY2 = os.getenv("CLOVA_SECRET_KEY2")

def run_ocr(image_path: str):
    
    # 파일 확장자 알아내기
    try:
        file_format = image_path.split('.')[-1]
    except IndexError:
        raise OCRError("파일 확장자가 없는 잘못된 경로입니다.")

    # 데이터 형식 구성
    request_json = {
        'images': [{'format': file_format, 'name': 'ocr_image'}],
        'requestId': str(uuid.uuid4()),
        'version': 'V2',
        'timestamp': int(round(time.time() * 1000))
    }

    payload = {'message': json.dumps(request_json).encode('UTF-8')}
    
    # 파일 열어서 API로 전송 후 결과 반환
    try:
        with open(image_path, 'rb') as f:
            files = [('file', f)]
            headers = {'X-OCR-SECRET': SECRET_KEY2}
            
            response = requests.post(API_URL, headers=headers, data=payload, files=files)

            if response.status_code != 200:
                raise OCRError(f"API Error - Status: {response.status_code}, Msg: {response.text}")
            
            return response.json()

    except FileNotFoundError:
        raise OCRError(f"서버에서 파일을 찾을 수 없습니다: {image_path}")
    except Exception as e:
        # requests 라이브러리 관련 오류 등 다른 모든 예외를 포함
        raise OCRError(f"OCR 실행 중 알 수 없는 오류: {e}")
