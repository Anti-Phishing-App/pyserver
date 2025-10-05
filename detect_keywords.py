# detect_keywords.py

KEYWORD_SCORES = {
    "송금": 10, "이체": 10, "안전계좌": 10, "보안계좌": 10, "현금 전달": 10, 
    "구속": 10, "형사처벌": 10,
    "검찰": 5, "경찰": 5, "금융감독원": 5, "법원": 5, "압류": 5, "긴급": 5, 
    "즉시": 5, "피의자": 5, "명의 도용": 5,
    "계좌": 2, "벌금": 2, "사건 번호": 2, "개인정보 유출": 2, "확인요망": 2, 
    "출석요구서": 2, "국세청": 2
}

def detect_keywords(ocr_result: dict):

    found_details = []
    found_unique_keywords = set()
    total_score = 0

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
    if not found_details:
        return {"risk_level": "없음", "total_score": 0, "details": []}

    if total_score >= 15:
        risk_level = "높음"
    elif total_score >= 8:
        risk_level = "중간"
    else:
        risk_level = "낮음"
        
    # 딕셔너리 형태로 최종 결과 반환
    return {
        "risk_level": risk_level,
        "total_score": total_score,
        "details": found_details
    }