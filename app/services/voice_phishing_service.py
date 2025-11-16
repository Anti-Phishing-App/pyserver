"""
보이스피싱 탐지 서비스

KoBERT 모델과 단어 기반 위험도 측정을 사용하여 텍스트가 보이스피싱인지 탐지합니다.
하이브리드 방식으로 즉시 응답(단어 기반)과 누적 분석(KoBERT)을 모두 지원합니다.
"""
import torch
import numpy as np
from typing import Dict, Tuple, List, Optional
from konlpy.tag import Okt
import pandas as pd
from collections import deque
from pathlib import Path
import os
import time
import uuid
import json

# 프로젝트 루트 경로
BASE_DIR = Path(__file__).resolve().parent.parent.parent
LOG_DIR = Path(os.getenv("PHISHING_LOG_DIR", BASE_DIR / "data" / "conversations"))
LOG_DIR.mkdir(parents=True, exist_ok=True)


def lazy_import_kobert():
    """
    KoBERT 관련 모듈을 지연 로딩

    KoBERT 의존성이 없을 경우 명확한 에러 메시지를 제공합니다.

    Returns:
        Tuple: (BERTClassifier, get_kobert_model, get_tokenizer)

    Raises:
        ImportError: KoBERT 의존성이 설치되지 않은 경우
    """
    try:
        from app.ml.kobert_classifier.BERTClassifier import BERTClassifier
        from kobert_transformers import get_kobert_model, get_tokenizer
        return BERTClassifier, get_kobert_model, get_tokenizer
    except ImportError as e:
        raise ImportError(
            f"KoBERT 의존성을 로드할 수 없습니다: {e}\n"
            "다음 패키지를 설치하세요: pip install kobert-transformers torch konlpy pandas transformers"
        )


class VoicePhishingDetector:
    """
    보이스피싱 탐지기

    KoBERT 딥러닝 모델과 단어 기반 통계 분석을 결합하여
    보이스피싱 여부를 판단합니다.

    Features:
        - KoBERT 모델을 통한 정확한 보이스피싱 분류
        - 단어 가중치 기반 실시간 위험도 계산
        - 범죄 유형 분류 (대출사기형 vs 수사기관사칭형)

    Attributes:
        bertmodel: KoBERT 기반 모델
        tokenizer: KoBERT 토크나이저
        device: 연산 장치 (cuda 또는 cpu)
        model: 학습된 BERTClassifier 모델
        okt: Okt 형태소 분석기
        df: 위험 단어 가중치 데이터프레임
        type_df: 범죄 유형별 단어 가중치 데이터프레임

    Example:
        >>> detector = VoicePhishingDetector()
        >>> result = detector.detect("대출 상담 도와드리겠습니다")
        >>> print(result['is_phishing'])  # True/False
    """

    def __init__(self):
        """보이스피싱 탐지기 초기화"""
        self.device = torch.device("cuda:0") if torch.cuda.is_available() else torch.device("cpu")
        self.BERTClassifier = None
        self.bertmodel = None
        self.tokenizer = None
        self.model = None
        self._kobert_ready = False
        self._kobert_error: Optional[Exception] = None

        self.kobert_threshold = float(os.getenv("PHISHING_KOBERT_THRESHOLD", "0.35"))

        # 단어 기반 탐지 초기화
        self.okt = Okt()
        self.df = pd.read_csv(BASE_DIR / "data/csv/500_가중치.csv", encoding='utf-8')
        self.type_df = pd.read_csv(BASE_DIR / "data/csv/type_token_가중치.csv", encoding='utf-8')

    def _ensure_kobert_ready(self):
        """
        KoBERT 모델이 필요한 시점에만 로딩하여 네트워크 의존성을 늦춘다.
        """
        if self._kobert_ready:
            return
        if self._kobert_error:
            raise self._kobert_error

        try:
            BERTClassifier, get_kobert_model, get_tokenizer = lazy_import_kobert()
            self.BERTClassifier = BERTClassifier
            self.bertmodel = get_kobert_model()
            self.tokenizer = get_tokenizer()
            self.model = self.BERTClassifier(self.bertmodel, dr_rate=0.4).to(self.device)
            model_path = BASE_DIR / "data/models/kobert/train.pt"
            self.model.load_state_dict(torch.load(model_path, map_location=self.device), strict=False)
            self.model.eval()
            self._kobert_ready = True
        except Exception as exc:  # KoBERT 초기화 실패 시 예외를 기억해 두고 재사용
            self._kobert_error = exc
            raise

    def _predict_kobert(self, text: str) -> Tuple[bool, float]:
        """
        KoBERT 모델로 보이스피싱 여부 예측

        Args:
            text: 분석할 텍스트

        Returns:
            Tuple[bool, float]: (보이스피싱 여부, 신뢰도)
                - is_phishing: True이면 보이스피싱, False이면 일반 전화
                - confidence: 예측 신뢰도 (0.0 ~ 1.0)
        """
        self._ensure_kobert_ready()

        inputs = self.tokenizer(
            text,
            return_tensors='pt',
            truncation=True,
            padding='max_length',
            max_length=64
        )

        token_ids = inputs['input_ids'].to(self.device)
        attention_mask = inputs['attention_mask'].to(self.device)
        token_type_ids = inputs.get('token_type_ids', torch.zeros_like(token_ids)).to(self.device)

        # 모델 추론
        with torch.no_grad():
            # valid_length 계산 (attention_mask의 합)
            valid_length = attention_mask.sum(dim=1)

            out = self.model(token_ids, valid_length, token_type_ids)

            logits = out.detach().cpu().numpy()

            # Confidence 계산 (softmax)
            exp_logits = np.exp(logits - np.max(logits))
            softmax = exp_logits / exp_logits.sum()
            prob_phishing = float(softmax[0][1])

            threshold = getattr(self, "kobert_threshold", float(os.getenv("PHISHING_KOBERT_THRESHOLD", "0.35")))
            self.kobert_threshold = threshold
            is_phishing = bool(prob_phishing >= threshold)
            confidence = prob_phishing

            return is_phishing, confidence

    def _calculate_risk_level(self, text: str) -> Tuple[int, float, str, List[str], List[Dict]]:
        """
        단어 기반 위험도 계산

        텍스트에서 위험 단어를 추출하고 가중치를 합산하여 위험도를 계산합니다.

        Args:
            text: 분석할 텍스트

        Returns:
            Tuple[int, float, str, List[str], List[Dict]]:
                - level: 위험도 레벨 (0: 안전, 1: 의심, 2: 경고, 3: 위험)
                - probability: 위험 점수 (0 ~ 100)
                - phishing_type: 범죄 유형 (대출사기형 or 수사기관사칭형)
                - keywords: 탐지된 위험 단어 목록
                - keyword_details: 각 단어의 가중치와 점수 상세 정보
        """
        RISK_THRESHOLD = 1.3  # 위험 단어 최소 가중치 (1.3 이상만 위험 단어로 간주)
        risk_score = 0.0
        type1_score = 0.0
        type2_score = 0.0
        token_dict = {}
        detected_keywords = []
        keyword_details = []  # 단어별 상세 정보

        # 형태소 분석 (명사, 부사만 추출)
        token_ko = pd.DataFrame(self.okt.pos(text), columns=['단어', '형태소'])
        token_ko = token_ko[(token_ko['단어'].str.len() > 1) & (token_ko.형태소.isin(['Noun', 'Adverb']))]

        # 위험도 계산 (위험 단어의 가중치를 합산)
        for word in token_ko.단어.values:
            if word in self.df.단어.values:
                weight = float(self.df.loc[self.df.단어 == word, '확률'].iloc[0])

                # 고위험 단어만 카운트 (가중치 1.3 이상)
                if weight >= RISK_THRESHOLD:
                    # 가중치를 점수로 변환: (weight - 1.0) * 10으로 정규화
                    # 예: 1.3 -> 3점, 1.5 -> 5점, 1.9 -> 9점
                    word_score = (weight - 1.0) * 10
                    risk_score += word_score

                    if word not in token_dict:
                        token_dict[word] = 1
                        detected_keywords.append(word)
                        # 상세 정보 추가
                        keyword_details.append({
                            'word': word,
                            'weight': round(weight, 4),
                            'score': round(word_score, 2)
                        })
                    else:
                        token_dict[word] = token_dict.get(word) + 1

        # 위험도 점수를 0-100 범위로 정규화
        probability = min(risk_score, 100.0)

        # 위험도 레벨 결정 (재조정된 임계값)
        if probability < 3.0:
            level = 0  # 안전 (위험 단어 없음)
        elif probability < 8.0:
            level = 1  # 의심 (위험 단어 1-2개)
        elif probability < 15.0:
            level = 2  # 경고 (위험 단어 3개 이상 또는 고위험 단어)
        else:
            level = 3  # 위험 (위험 단어 다수 또는 매우 고위험 단어)

        # 범죄 유형 분류
        if len(token_dict) == 0:
            phishing_type = None
        else:
            token_df = pd.DataFrame(zip(token_dict.keys(), token_dict.values()), columns=['의심 단어', '횟수'])
            token_df = token_df.sort_values(by='횟수', ascending=False)

            for word, count in zip(token_df['의심 단어'].values, token_df['횟수'].values):
                if word in self.type_df.type1_단어.values:
                    weight = float(self.type_df.loc[self.type_df.type1_단어 == word, 'type1_확률'].iloc[0])
                    type1_score += (weight - 1.0) * 10 * count
                elif word in self.type_df.type2_단어.values:
                    weight = float(self.type_df.loc[self.type_df.type2_단어 == word, 'type2_확률'].iloc[0])
                    type2_score += (weight - 1.0) * 10 * count

            phishing_type = '대출사기형' if type1_score > type2_score else '수사기관사칭형'

        return level, probability, phishing_type, detected_keywords, keyword_details

    def detect_immediate(self, text: str) -> Dict:
        """
        즉시 응답 - 단어 기반 탐지 (실시간 분석용)

        문장 단위로 빠르게 위험도를 분석합니다.
        WebSocket 실시간 스트리밍에 적합합니다.

        Args:
            text: 분석할 텍스트 (문장 단위)

        Returns:
            Dict: 탐지 결과
                - level: 위험도 레벨 (0: 안전, 1: 의심, 2: 경고, 3: 위험)
                - probability: 위험 확률
                - phishing_type: 범죄 유형
                - keywords: 탐지된 위험 단어
                - keyword_details: 각 단어의 가중치 정보
                - method: 'word_based'

        Example:
            >>> result = detector.detect_immediate("대출 상담 도와드리겠습니다")
            >>> print(result['level'])  # 1, 2, 3
        """
        min_len = int(os.getenv("PHISHING_IMMEDIATE_MIN_CHARS", "3"))
        normalized = (text or "").strip()
        if not normalized or len(normalized) < min_len:
            return {
                'level': 0,
                'probability': 0.0,
                'phishing_type': None,
                'keywords': [],
                'keyword_details': [],
                'method': 'word_based'
            }

        level, probability, phishing_type, keywords, keyword_details = self._calculate_risk_level(normalized)
        return {
            'level': level,
            'probability': probability,
            'phishing_type': phishing_type,
            'keywords': keywords,
            'keyword_details': keyword_details,
            'method': 'word_based'
        }

    @staticmethod
    def level_from_probability(probability: float) -> int:
        if probability < 3.0:
            return 0
        if probability < 8.0:
            return 1
        if probability < 15.0:
            return 2
        return 3

    def detect_comprehensive(self, text: str) -> Dict:
        """
        종합 분석 - KoBERT 모델 (누적 분석용)

        여러 문장이 누적된 대화 전체를 KoBERT로 분석합니다.
        정확도가 높지만 처리 시간이 필요합니다.

        Args:
            text: 분석할 텍스트 (여러 문장 누적)

        Returns:
            Dict: 탐지 결과
                - is_phishing: 보이스피싱 여부
                - confidence: 예측 신뢰도
                - method: 'kobert'
                - analyzed_length: 분석한 텍스트 길이

        Example:
            >>> accumulated = "대출 상담... 금리 낮습니다... 계좌번호 알려주세요"
            >>> result = detector.detect_comprehensive(accumulated)
            >>> print(result['is_phishing'])  # True/False
        """
        if not text or len(text.strip()) < 10:
            return {
                'is_phishing': False,
                'confidence': 0.0,
                'method': 'kobert',
                'analyzed_length': 0
            }

        is_phishing, confidence = self._predict_kobert(text)
        return {
            'is_phishing': is_phishing,
            'confidence': confidence,
            'method': 'kobert',
            'analyzed_length': len(text)
        }

    def detect(self, text: str) -> Dict:
        """
        전체 분석 (레거시 호환용)

        KoBERT로 보이스피싱 여부를 판단하고,
        보이스피싱으로 판단된 경우 위험도와 유형을 분석합니다.

        Args:
            text: 분석할 텍스트

        Returns:
            Dict: 탐지 결과
                - is_phishing: 보이스피싱 여부
                - level: 위험도 레벨
                - probability: 위험 확률
                - phishing_type: 범죄 유형

        Example:
            >>> result = detector.detect("대출 상담 계좌번호 알려주세요")
            >>> if result['is_phishing']:
            >>>     print(f"위험도: {result['level']}, 유형: {result['phishing_type']}")
        """
        if not text or len(text.strip()) < 10:
            return {
                'is_phishing': False,
                'level': 0,
                'probability': 0.0,
                'phishing_type': None
            }

        # KoBERT로 보이스피싱 여부 판단
        is_phishing, confidence = self._predict_kobert(text)

        if is_phishing:
            # 보이스피싱으로 판단된 경우 위험도 계산
            level, probability, phishing_type, keywords, keyword_details = self._calculate_risk_level(text)
            return {
                'is_phishing': True,
                'level': level,
                'probability': probability,
                'phishing_type': phishing_type,
                'confidence': confidence,
                'keywords': keywords,
                'keyword_details': keyword_details
            }
        else:
            return {
                'is_phishing': False,
                'level': 0,
                'probability': 0.0,
                'phishing_type': None,
                'confidence': confidence
            }


class HybridPhishingSession:
    """
    하이브리드 보이스피싱 탐지 세션

    실시간 음성 인식 스트리밍에 최적화된 하이브리드 탐지 방식:
    - 즉시 응답: 문장 단위 단어 기반 탐지 (빠름)
    - 누적 분석: 누적 텍스트가 10자 이상일 때마다 KoBERT 분석 (정확함)

    Attributes:
        detector: VoicePhishingDetector 인스턴스
        window_size: 버퍼 크기 (문장 수)
        sentence_buffer: 최근 문장 버퍼
        accumulated_text: 누적된 전체 텍스트
        kobert_result: 최근 KoBERT 분석 결과
        sentence_count: 누적 문장 수

    Example:
        >>> detector = VoicePhishingDetector()
        >>> session = HybridPhishingSession(detector, window_size=5)
        >>>
        >>> # WebSocket에서 문장이 들어올 때마다
        >>> result = session.add_sentence("대출 상담 도와드리겠습니다")
        >>> print(result['immediate'])  # 즉시 응답
        >>> print(result['comprehensive'])  # KoBERT 분석 (3문장 이상일 때)
    """

    def __init__(self, detector: VoicePhishingDetector, window_size: int = 5):
        """
        하이브리드 세션 초기화

        Args:
            detector: VoicePhishingDetector 인스턴스
            window_size: 버퍼에 유지할 최대 문장 수 (기본값: 5)
        """
        self.detector = detector
        self.window_size = window_size
        self.sentence_buffer = deque(maxlen=window_size)
        self.accumulated_text = ""
        self.kobert_result = None
        self.sentence_count = 0
        self.min_sentences_for_kobert = int(os.getenv("PHISHING_KOBERT_MIN_SENTENCES", "1"))
        self.min_chars_for_kobert = int(os.getenv("PHISHING_KOBERT_MIN_CHARS", "6"))
        self.kobert_threshold = self._float_env("PHISHING_KOBERT_THRESHOLD", 0.35)

        # 실시간 누적 상태
        self.cumulative_probability = 0.0
        self.cumulative_keywords: List[str] = []
        self._keyword_counts: Dict[str, int] = {}
        self.cumulative_keyword_details: List[Dict] = []
        self._keyword_detail_keys: set[Tuple] = set()
        self.cumulative_phishing_type: Optional[str] = None
        self._risk_gain = self._float_env("PHISHING_IMMEDIATE_RISK_GAIN", 1.0)
        self._safe_decay = self._float_env("PHISHING_IMMEDIATE_SAFE_DECAY", 1.5)
        self.conversation_log: List[Dict] = []
        self.session_id = uuid.uuid4().hex
        self.started_at = time.time()
        self.current_sentence = ""
        self.force_final_enabled = os.getenv("PHISHING_FORCE_FINAL", "true").lower() in {"1", "true", "yes", "on"}

    @staticmethod
    def _float_env(name: str, default: float) -> float:
        try:
            return float(os.getenv(name, default))
        except (TypeError, ValueError):
            return default

    def _merge_keywords(self, immediate_result: Dict):
        for kw in immediate_result.get('keywords', []) or []:
            kw = kw or ''
            if not kw:
                continue
            count = self._keyword_counts.get(kw, 0) + 1
            self._keyword_counts[kw] = count
            self.cumulative_keywords.append(kw)
        for detail in immediate_result.get('keyword_details', []) or []:
            key = tuple(sorted(detail.items()))
            if key not in self._keyword_detail_keys:
                self._keyword_detail_keys.add(key)
                self.cumulative_keyword_details.append(detail)

    def _update_cumulative_immediate(self, immediate_result: Optional[Dict]) -> Dict:
        if not immediate_result:
            return self._current_cumulative_snapshot()

        level = immediate_result.get('level', 0) or 0
        probability = float(immediate_result.get('probability') or 0.0)

        if level > 0:
            keywords = immediate_result.get('keywords') or []
            repeat_factor = 1.0
            if keywords:
                factors = []
                for kw in keywords:
                    kw = kw or ''
                    if not kw:
                        continue
                    prev = self._keyword_counts.get(kw, 0)
                    factors.append(1.0 / (1 + prev))
                if factors:
                    repeat_factor = sum(factors) / len(factors)
            delta = probability * self._risk_gain * repeat_factor
            self.cumulative_probability = min(100.0, self.cumulative_probability + delta)
            phishing_type = immediate_result.get('phishing_type')
            if phishing_type:
                self.cumulative_phishing_type = phishing_type
            self._merge_keywords(immediate_result)
        else:
            self.cumulative_probability = max(0.0, self.cumulative_probability - self._safe_decay)

        return self._current_cumulative_snapshot()

    def _current_cumulative_snapshot(self) -> Dict:
        level = self.detector.level_from_probability(self.cumulative_probability)
        return {
            'level': level,
            'probability': round(self.cumulative_probability, 2),
            'phishing_type': self.cumulative_phishing_type,
            'keywords': list(self.cumulative_keywords),
            'keyword_details': list(self.cumulative_keyword_details),
            'method': 'word_based_cumulative'
        }

    def process_fragment(self, sentence: str, is_final: bool) -> Dict:
        """
        실시간 조각을 처리하여 누적 위험도 및 종합 분석을 반환한다.
        """
        if not sentence or not sentence.strip():
            return {
                'chunk_immediate': None,
                'immediate': self._current_cumulative_snapshot(),
                'comprehensive': None
            }

        immediate_result = self.detector.detect_immediate(sentence)
        cumulative_snapshot = self._update_cumulative_immediate(immediate_result)

        self.current_sentence = (f"{self.current_sentence} {sentence}".strip()).strip()
        effective_final = False
        final_sentence = None
        if self.current_sentence:
            if bool(is_final):
                effective_final = True
                final_sentence = self.current_sentence
                self.current_sentence = ""
            elif self._should_force_finalize(self.current_sentence):
                effective_final = True
                final_sentence = self.current_sentence
                self.current_sentence = ""

        comprehensive_result = None
        if effective_final and final_sentence:
            final_immediate = self.detector.detect_immediate(final_sentence)
            sentence_result = self.add_sentence(final_sentence, immediate_result=final_immediate)
            comprehensive_result = sentence_result.get('comprehensive')
            self._append_history(final_sentence, True, final_immediate, cumulative_snapshot)
        else:
            self._append_history(sentence, False, immediate_result, cumulative_snapshot)

        return {
            'chunk_immediate': immediate_result,
            'immediate': cumulative_snapshot,
            'comprehensive': comprehensive_result,
            'history': self.get_conversation_log(),
            'session_id': self.session_id
        }

    def _should_force_finalize(self, sentence: str) -> bool:
        if not self.force_final_enabled:
            return False
        text = (sentence or "").strip()
        if len(text) < self.min_chars_for_kobert:
            return False
        if text[-1:] in {".", "!", "?", "다", "요"}:
            return True
        if text.count(" ") >= 2:
            return True
        return False

    def _append_history(self, sentence: str, is_final: bool, chunk_immediate: Dict, cumulative_snapshot: Dict):
        if not is_final or not sentence:
            return
        self.conversation_log.append({
            'text': sentence,
            'is_final': True,
            'timestamp': time.time(),
            'chunk_immediate': chunk_immediate,
            'immediate': cumulative_snapshot
        })

    def get_conversation_log(self) -> List[Dict]:
        return list(self.conversation_log)

    def _persist_conversation(self):
        if not self.conversation_log:
            return
        record = {
            'session_id': self.session_id,
            'started_at': self.started_at,
            'ended_at': time.time(),
            'log': self.conversation_log,
        }
        target = LOG_DIR / f"{self.session_id}.json"
        with target.open('w', encoding='utf-8') as fp:
            json.dump(record, fp, ensure_ascii=False, indent=2)

    def add_sentence(self, sentence: str, immediate_result: Optional[Dict] = None) -> Dict:
        """
        문장 추가 및 분석

        새로운 문장을 추가하고 즉시 단어 기반 분석을 수행합니다.
        누적 텍스트가 충분해지면 KoBERT 종합 분석도 수행합니다.

        Args:
            sentence: 새로 추가할 문장

        Returns:
            Dict:
                - immediate: 단어 기반 즉시 분석 결과
                - comprehensive: KoBERT 종합 분석 결과 (누적 텍스트 10자 이상일 때)

        Example:
            >>> result = session.add_sentence("계좌번호 알려주세요")
            >>> if result['immediate']['level'] >= 2:
            >>>     print("경고! 위험한 단어 감지")
        """
        if not sentence or len(sentence.strip()) < 5:
            return {
                'immediate': None,
                'comprehensive': None
            }

        # 문장 버퍼에 추가
        self.sentence_buffer.append(sentence)
        self.accumulated_text += " " + sentence
        self.sentence_count += 1

        # 즉시 응답 (단어 기반) - 항상 실행
        immediate_result = immediate_result or self.detector.detect_immediate(sentence)

        # 누적 분석 (KoBERT) - 누적 텍스트 길이가 충분할 때마다 실행
        comprehensive_result = None
        accumulated_text = self.accumulated_text.strip()
        if (self.sentence_count >= max(1, self.min_sentences_for_kobert) or len(accumulated_text) >= self.min_chars_for_kobert):
            comprehensive_result = self.detector.detect_comprehensive(accumulated_text)
            self.kobert_result = comprehensive_result

        return {
            'immediate': immediate_result,
            'comprehensive': comprehensive_result
        }

    def get_latest_comprehensive(self) -> Optional[Dict]:
        """
        가장 최근 KoBERT 분석 결과 반환

        Returns:
            Optional[Dict]: 최근 종합 분석 결과 (없으면 None)
        """
        return self.kobert_result

    def reset(self):
        """세션 초기화 (통화 종료 시 호출)"""
        self._persist_conversation()
        self.sentence_buffer.clear()
        self.accumulated_text = ""
        self.kobert_result = None
        self.sentence_count = 0
        self.cumulative_probability = 0.0
        self.cumulative_keywords.clear()
        self.cumulative_keyword_details.clear()
        self._keyword_detail_keys.clear()
        self.cumulative_phishing_type = None
        self.conversation_log.clear()
        self._keyword_counts.clear()
        self.session_id = uuid.uuid4().hex
        self.started_at = time.time()
        self.conversation_log.clear()
        self.current_sentence = ""


# ==========================================
# 싱글톤 인스턴스 관리
# ==========================================

_detector = None


def get_detector() -> VoicePhishingDetector:
    """
    보이스피싱 탐지기 싱글톤 인스턴스 반환

    모델 로딩은 무거운 작업이므로 전역에서 하나의 인스턴스만 사용합니다.

    Returns:
        VoicePhishingDetector: 탐지기 인스턴스
    """
    global _detector
    if _detector is None:
        _detector = VoicePhishingDetector()
    return _detector


def create_session(window_size: int = 5) -> HybridPhishingSession:
    """
    하이브리드 탐지 세션 생성

    Args:
        window_size: 버퍼 크기 (기본값: 5)

    Returns:
        HybridPhishingSession: 새로운 세션 인스턴스
    """
    detector = get_detector()
    return HybridPhishingSession(detector, window_size)
