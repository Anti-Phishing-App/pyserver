# ocr_run.py

import requests
import uuid
import time
import json
import os

API_URL = os.getenv('CLOVA_API_URL', 'https://fwymjktetd.apigw.ntruss.com/custom/v1/45162/f06f44fc9667be94a98feed9824ad4f1bb0c7a35bf9e32132fc012be76435739/general')
SECRET_KEY = os.getenv('CLOVA_SECRET_KEY', 'S0daUXhPRFJWZG9QdFJvdWtudFlkT0dObENZVE95QUg=')

def run_ocr(image_path: str):
    
    # 파일 확장자 알아내기
    try:
        file_format = image_path.split('.')[-1]
    except IndexError:
        return {"error": True, "message": "파일 확장자가 없는 잘못된 경로입니다."}

    # 데이터 형식 구성
    request_json = {
        'images': [{'format': file_format, 'name': 'ocr_image'}],
        'requestId': str(uuid.uuid4()),
        'version': 'V2',
        'timestamp': int(round(time.time() * 1000))
    }

    payload = {'message': json.dumps(request_json).encode('UTF-8')}
    
    # 파일 열어서 API로 전송
    try:
        with open(image_path, 'rb') as f:
            files = [('file', f)]
            headers = {'X-OCR-SECRET': SECRET_KEY}

            
            response = requests.post(API_URL, headers=headers, data=payload, files=files)
    
    except FileNotFoundError:
        return {"error": True, "message": f"서버에서 파일을 찾을 수 없습니다: {image_path}"}


    # 결과 return
    if response.status_code == 200:
        return response.json()  # 성공 시, JSON 결과를 딕셔너리로 변환하여 반환
    else:
        # 실패 시, main.py에서 처리할 수 있도록 에러 정보를 담은 딕셔너리를 반환
        return {
            "error": True,
            "status_code": response.status_code,
            "message": response.text
        }