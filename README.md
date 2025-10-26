# pyserver
python Fastapi server

### 디렉토리 구조

```
 pyserver/
  ├── app/
  │   ├── __init__.py
  │   ├── main.py                      # FastAPI 앱 초기화
  │   ├── config.py                    # 환경변수 관리
  │   │
  │   ├── core/                        # 핵심 기능
  │   │   ├── __init__.py
  │   │   ├── database.py              # DB 연결
  │   │   ├── security.py              # JWT, 비밀번호 해싱
  │   │   ├── dependencies.py          # 인증 의존성
  │   │   └── exceptions.py            # 커스텀 예외
  │   │
  │   ├── models/                      # ORM 모델 (DB 테이블)
  │   │   ├── __init__.py
  │   │   ├── user.py                  # 사용자
  │   │   └── detection_history.py     # 탐지 이력
  │   │
  │   ├── schemas/                     # Pydantic 스키마
  │   │   ├── __init__.py
  │   │   ├── auth.py                  # 로그인/회원가입
  │   │   └── user.py                  # 사용자 응답
  │   │
  │   ├── api/                         # API 라우터
  │   │   ├── __init__.py
  │   │   ├── auth.py                  # 인증
  │   │   ├── user.py                  # 사용자 관리
  │   │   ├── voice_phishing.py        # 보이스피싱 WebSocket
  │   │   ├── document_fraud.py        # 문서 위조
  │   │   ├── url_phishing.py          # 피싱 사이트
  │   │   ├── sms_phishing.py          # 문자 피싱
  │   │   └── upload.py                # 공통 업로드
  │   │
  │   ├── services/                    # 비즈니스 로직
  │   │   ├── __init__.py
  │   │   ├── auth_service.py
  │   │   ├── user_service.py
  │   │   ├── voice_phishing_service.py
  │   │   ├── document_fraud_service.py
  │   │   ├── url_phishing_service.py
  │   │   └── sms_phishing_service.py
  │   │
  │   ├── ml/                          # AI 모델
  │   │   ├── __init__.py
  │   │   ├── base.py                  # 베이스 클래스
  │   │   │
  │   │   ├── models/                  # 학습된 모델 파일
  │   │   │   ├── voice/
  │   │   │   │   ├── kobert_voice.pt
  │   │   │   │   └── word_weights.json
  │   │   │   ├── document/
  │   │   │   │   ├── stamp_detector.pt
  │   │   │   │   └── fraud_classifier.onnx
  │   │   │   ├── url/
  │   │   │   │   └── url_classifier.pkl
  │   │   │   └── sms/
  │   │   │       └── sms_classifier.pt
  │   │   │
  │   │   ├── predictors/              # 추론 클래스
  │   │   │   ├── __init__.py
  │   │   │   ├── voice_phishing_predictor.py
  │   │   │   ├── document_fraud_predictor.py
  │   │   │   ├── url_phishing_predictor.py
  │   │   │   └── sms_phishing_predictor.py
  │   │   │
  │   │   └── utils/                   # 전처리/후처리
  │   │       ├── __init__.py
  │   │       ├── text_preprocessor.py
  │   │       ├── image_preprocessor.py
  │   │       └── tokenizer.py
  │   │
  │   └── utils/                       # 공통 유틸
  │       ├── __init__.py
  │       ├── file_handler.py
  │       └── logger.py
  │
  ├── grpc/                            # gRPC (STT)
  │   ├── __init__.py
  │   ├── clova_grpc_client.py
  │   ├── nest_pb2.py
  │   ├── nest_pb2_grpc.py
  │   └── nest.proto
  │
  ├── legacy/                          # 기존 파일 (임시)
  │   ├── ocr_run.py
  │   ├── detect_keywords.py
  │   ├── layout_analysis.py
  │   └── stamp.py
  │
  ├── uploads/                         # 업로드 저장소
  ├── logs/                            # 로그
  ├── tests/                           # 테스트
  │
  ├── .env
  ├── .gitignore
  ├── requirements.txt
  ├── README.md
  └── index.html
```