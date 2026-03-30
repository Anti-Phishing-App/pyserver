"""
SMS 피싱 키워드 탐지 서비스

문서 OCR과 달리 SMS 메시지는 짧고 직접적인 텍스트 특성을 가지므로
SMS 피싱에 특화된 키워드와 패턴을 사용합니다.
"""

# SMS 피싱 특화 키워드 점수
SMS_KEYWORD_SCORES = {
    # 치명적 키워드 (스미싱 강력 의심, 0.5~0.7)
    "안전계좌": 0.7,
    "보안계좌": 0.7,
    "현금 전달": 0.6,
    "대포통장": 0.7,
    "계좌 이체": 0.5,
    "송금 요청": 0.5,
    "개인정보 확인": 0.5,
    "비밀번호 입력": 0.6,
    "인증번호 전송": 0.5,

    # 강력 경고 키워드 (금전/법적 행위 직접 유도, 0.3~0.5)
    "송금": 0.4,
    "이체": 0.4,
    "입금": 0.3,
    "구속": 0.5,
    "형사처벌": 0.5,
    "압류": 0.4,
    "고소": 0.3,
    "체포": 0.5,
    "영장": 0.4,
    "계좌번호": 0.4,
    "비밀번호": 0.4,
    "인증번호": 0.4,
    "OTP": 0.4,
    "보안카드": 0.4,

    # 기관 사칭 키워드 (압박감 조성, 0.2~0.3)
    "검찰": 0.3,
    "검찰청": 0.3,
    "경찰": 0.3,
    "경찰청": 0.3,
    "금융감독원": 0.3,
    "금감원": 0.3,
    "법원": 0.3,
    "국세청": 0.2,
    "관세청": 0.2,
    "우체국": 0.2,
    "은행": 0.2,
    "카드사": 0.2,
    "통신사": 0.2,

    # 긴급성/특정 행위 유도 키워드 (0.2~0.3)
    "긴급": 0.3,
    "즉시": 0.3,
    "24시간 이내": 0.3,
    "오늘 중": 0.3,
    "피의자": 0.3,
    "명의 도용": 0.3,
    "개인정보 유출": 0.3,
    "사건 번호": 0.2,
    "출석요구서": 0.2,
    "소환장": 0.2,
    "전화 주세요": 0.2,
    "연락 바랍니다": 0.2,
    "클릭": 0.2,
    "링크": 0.2,
    "앱 설치": 0.3,
    "프로그램 설치": 0.3,

    # 금융/대출 관련 키워드 (0.1~0.2)
    "대출": 0.2,
    "저금리": 0.2,
    "신용": 0.1,
    "한도": 0.1,
    "승인": 0.1,
    "연체": 0.2,
    "채무": 0.2,
    "미납": 0.2,
    "미수": 0.2,
    "정지": 0.2,
    "해지": 0.2,

    # 택배/쿠폰 사칭 (0.1~0.2)
    "택배": 0.1,
    "배송": 0.1,
    "상품권": 0.2,
    "쿠폰": 0.1,
    "당첨": 0.2,
    "경품": 0.2,
    "무료": 0.1,

    # 주의 키워드 (문맥 강화, 0.1)
    "계좌": 0.1,
    "벌금": 0.2,
    "확인요망": 0.2,
    "확인하세요": 0.1,
    "조회": 0.1,
    "인증": 0.1,
}


def detect_sms_keywords(text: str) -> dict:
    """
    SMS 텍스트에서 피싱 키워드를 탐지합니다.

    Args:
        text: SMS 텍스트 (문장 리스트를 결합한 전체 텍스트)

    Returns:
        dict: {
            "total_score": float (0.0~1.0),
            "keywords": list[str] (탐지된 키워드 목록),
            "details": list[dict] (키워드별 상세 정보),
            "risk_level": int (0~3)
        }
    """
    try:
        found_details = []
        found_unique_keywords = set()
        total_score = 0.0

        # 텍스트에서 키워드 검출
        for kw, score in SMS_KEYWORD_SCORES.items():
            if kw in text and kw not in found_unique_keywords:
                found_details.append({
                    "keyword": kw,
                    "score": score
                })
                found_unique_keywords.add(kw)
                total_score += score

        # 총점 제한 (최대 1.0)
        total_score = min(total_score, 1.0)

        # 위험도 레벨 결정
        if total_score >= 0.7:
            risk_level = 3  # 위험
        elif total_score >= 0.5:
            risk_level = 2  # 경고
        elif total_score >= 0.3:
            risk_level = 1  # 의심
        else:
            risk_level = 0  # 안전

        return {
            "total_score": round(total_score, 2),
            "keywords": list(found_unique_keywords),
            "details": found_details,
            "risk_level": risk_level
        }

    except Exception as e:
        return {
            "error": True,
            "message": str(e),
            "total_score": 0.0,
            "keywords": [],
            "details": [],
            "risk_level": 0
        }


def detect_sms_keywords_batch(texts: list) -> dict:
    """
    여러 SMS 텍스트를 결합하여 키워드를 탐지합니다.

    Args:
        texts: SMS 텍스트 문장 목록

    Returns:
        detect_sms_keywords() 반환값과 동일
    """
    full_text = " ".join(texts)
    return detect_sms_keywords(full_text)
