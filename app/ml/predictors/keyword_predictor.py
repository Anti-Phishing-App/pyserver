"""키워드 탐지 모듈"""

# 기존 detect_keywords.py 코드를 구조에 맞추어 옮겨 작성함.

KEYWORD_SCORES = {
    # 치명적 키워드 (이 단어 하나만으로도 스미싱이 강력 의심됨)
    "안전계좌": 0.6, "보안계좌": 0.6, "현금 전달": 0.6,
    
    # 강력 경고 키워드 (금전, 법적 행위 직접 유도)
    "송금": 0.4, "이체": 0.4, "구속": 0.4, "형사처벌": 0.4, "압류": 0.3,
    
    # 기관/권위 사칭 키워드 (압박감 조성)
    "검찰": 0.2, "경찰": 0.2, "금융감독원": 0.2, "법원": 0.2, "국세청": 0.1,
    
    # 긴급성/특정 행위 유도 키워드
    "긴급": 0.2, "즉시": 0.2, "피의자": 0.2, "명의 도용": 0.2, "개인정보 유출": 0.2,
    "사건 번호": 0.1, "출석요구서": 0.1, 
    
    # 주의 키워드 (문맥 강화)
    "계좌": 0.1, "벌금": 0.1, "확인요망": 0.1
}

def detect_keywords(ocr_result: dict):
    try:

        found_details = []
        found_unique_keywords = set()
        total_score = 0.0

        # OCR 결과에서 텍스트 순회하며 키워드 검출
        for image in ocr_result.get("images", []):
            for field in image.get("fields", []):
                text = field.get("inferText", "")
                for kw, score in KEYWORD_SCORES.items():
                    if kw in text and kw not in found_unique_keywords:
                        found_details.append({"keyword": kw, "full_text": text, "score": score})
                        found_unique_keywords.add(kw)
                        total_score += score
    
        # 총점에 따라 위험도 결정
        total_score = min(total_score, 1.0)

        if not found_details:
            return {
                "error": False,
                "total_score": 0,
                "details": []
            }
        
        # 딕셔너리 형태로 최종 결과 반환
        return {
            "error": False,
            "total_score": round(total_score, 2), # 소수점 둘째 자리까지 반올림
            "details": found_details
        }
    
    except Exception as e:
        return {"error": True, "message": str(e)}
