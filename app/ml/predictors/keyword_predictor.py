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

        # ✅ OCR 통계(문서 판별용)
        ocr_field_count = 0
        ocr_text_len = 0

        # OCR 결과에서 텍스트 순회하며 키워드 검출
        for image in ocr_result.get("images", []):
            for field in image.get("fields", []):
                text = (field.get("inferText", "") or "").strip()

                # 통계 누적
                if text:
                    ocr_field_count += 1
                    ocr_text_len += len(text)

                # 키워드 탐지
                for kw, score in KEYWORD_SCORES.items():
                    if text and kw in text and kw not in found_unique_keywords:
                        found_details.append({"keyword": kw, "full_text": text, "score": score})
                        found_unique_keywords.add(kw)
                        total_score += score

        total_score = min(total_score, 1.0)

        # 문서 판별
        # TODO : threshold는 운영하면서 튜닝
        is_document = (ocr_field_count > 0 and ocr_text_len >= 15)

        # 결과 반환
        # ocr field count 및 text len은 인식된 텍스트 조각 수 & 전체 텍스트 길이이므로 굳이 최종 결과에 반환 안함 (문서인지 아닌지 확인 위한 변수)
        return {
            "error": False,
            "total_score": round(total_score, 2),
            "details": found_details,
            "is_document": is_document
        }

    except Exception as e:
        return {"error": True, "message": str(e), "ocr_field_count": 0, "ocr_text_len": 0, "is_document": False}
