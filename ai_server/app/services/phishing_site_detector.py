"""
피싱 사이트 탐지 모듈
Random Forest 모델과 URL 기반 위험도 측정을 사용하여 URL이 피싱 사이트인지 탐지
하이브리드 방식: 즉시 응답(URL 기반) + 종합 분석(ML 모델 + PhishTank DB)
"""
import re
import pickle
import requests
import pandas as pd
from typing import Dict, Tuple, List
from pathlib import Path
from urllib.parse import urlparse
from bs4 import BeautifulSoup

# 프로젝트 루트 경로
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# 29개 특징 이름
FEATURE_NAMES = [
    'length_url', 'length_hostname', 'ip', 'nb_dots', 'nb_qm', 'nb_eq', 'nb_slash',
    'nb_www', 'ratio_digits_url', 'ratio_digits_host', 'tld_in_subdomain', 'prefix_suffix',
    'shortest_word_host', 'longest_words_raw', 'longest_word_path', 'phish_hints',
    'nb_hyperlinks', 'ratio_intHyperlinks', 'empty_title', 'domain_in_title', 'domain_age',
    'google_index', 'page_rank', 'nb_hyperlinks.1', 'ratio_intHyperlinks.1', 'empty_title.1',
    'Favicon', 'Request_URL', 'URL_of_Anchor', 'Links_in_tags', 'SFH', 'Iframe'
]


class PhishingSiteDetector:
    def __init__(self):
        """피싱 사이트 탐지기 초기화"""
        # ML 모델 로드
        model_path = BASE_DIR / "data/models/phishing_site/rf_29features_0603.pkl"
        scaler_path = BASE_DIR / "data/models/phishing_site/rf_29features_scaler_0603.pkl"

        with open(model_path, 'rb') as f:
            self.model = pickle.load(f)

        with open(scaler_path, 'rb') as f:
            self.scaler = pickle.load(f)

        # PhishTank DB (나중에 로드)
        self.phishtank_db = set()
        self._load_phishtank_db()

        print("✅ PhishingSiteDetector initialized successfully")

    def _load_phishtank_db(self):
        """PhishTank DB 로드"""
        db_path = BASE_DIR / "data/phishtank/phishing_urls.txt"
        if db_path.exists():
            with open(db_path, 'r') as f:
                self.phishtank_db = set(line.strip() for line in f if line.strip())
            print(f"✅ Loaded {len(self.phishtank_db)} phishing URLs from PhishTank DB")
        else:
            print("⚠️  PhishTank DB not found. Will use ML model only.")

    def _extract_url_features(self, url: str) -> Dict:
        """URL에서 특징 추출 (크롤링 없이 URL만 사용)"""
        parsed = urlparse(url)
        domain = parsed.netloc
        features = {}

        # URL 기반 특징 (빠름)
        features['length_url'] = len(url)
        features['length_hostname'] = len(domain)
        features['ip'] = 1 if re.match(r"^\d{1,3}(\.\d{1,3}){3}$", domain) else 0
        features['nb_dots'] = url.count('.')
        features['nb_qm'] = url.count('?')
        features['nb_eq'] = url.count('=')
        features['nb_slash'] = url.count('/')
        features['nb_www'] = url.count('www')
        features['ratio_digits_url'] = sum(c.isdigit() for c in url) / len(url) if url else 0
        features['ratio_digits_host'] = sum(c.isdigit() for c in domain) / len(domain) if domain else 0
        features['tld_in_subdomain'] = 1 if re.search(r'\.(com|net|org|info)', parsed.netloc.split('.')[0]) else 0

        # 신뢰 도메인 제외하고 하이픈 체크
        features['prefix_suffix'] = 0 if any(x in domain for x in ['azure', 'google', 'amazonaws', 'akamai', 'cloudfront']) else (1 if '-' in domain else 0)

        words_host = domain.split('.')
        path = parsed.path.split('/')
        features['shortest_word_host'] = min((len(word) for word in words_host), default=0)
        features['longest_words_raw'] = max((len(word) for word in url.split('/')), default=0)
        features['longest_word_path'] = max((len(word) for word in path), default=0)

        # 피싱 힌트 키워드 (개수도 함께 반환)
        hints = ['secure', 'account', 'update', 'verify', 'login', 'confirm', 'suspend', 'alert',
                 'banking', 'wallet', 'password', 'auth', 'credential']
        url_lower = url.lower()
        matched_hints = [h for h in hints if h in url_lower]
        features['phish_hints'] = 1 if matched_hints else 0
        features['phish_hints_count'] = len(matched_hints)

        # 단축 URL 탐지
        shorteners = ['bit.ly', 'tinyurl.com', 't.co', 'goo.gl', 'ow.ly', 'short.link']
        features['is_shortener'] = 1 if any(s in domain for s in shorteners) else 0

        # 의심스러운 TLD
        suspicious_tlds = ['.xyz', '.top', '.club', '.info', '.online', '.site', '.work']
        features['suspicious_tld'] = 1 if any(domain.endswith(tld) for tld in suspicious_tlds) else 0

        # 숫자로만 된 서브도메인 체크
        subdomain_parts = domain.split('.')
        features['numeric_subdomain'] = 1 if len(subdomain_parts) > 2 and subdomain_parts[0].isdigit() else 0

        return features, domain

    def _extract_html_features(self, url: str, domain: str) -> Dict:
        """HTML 크롤링 특징 추출 (느림)"""
        features = {}

        try:
            response = requests.get(url, timeout=3, allow_redirects=True)
            soup = BeautifulSoup(response.content, 'html.parser')

            # 하이퍼링크 분석
            all_links = soup.find_all('a')
            features['nb_hyperlinks'] = len(all_links)

            internal_links = [a for a in all_links if domain in (a.get('href') or '')]
            features['ratio_intHyperlinks'] = len(internal_links) / len(all_links) if all_links else 0

            # 타이틀 분석
            features['empty_title'] = 1 if not (soup.title and soup.title.string and soup.title.string.strip()) else 0
            features['domain_in_title'] = 1 if soup.title and domain.split('.')[-2] in soup.title.string.lower() else 0

            # Favicon
            favicon = soup.find("link", rel=lambda x: x and 'icon' in x.lower())
            if favicon and 'href' in favicon.attrs:
                href = favicon['href']
                features['Favicon'] = 1 if domain not in href else 0
            else:
                features['Favicon'] = 0

            # 기타 특징
            features['URL_of_Anchor'] = 1 if any(a.get('href', '').startswith('#') for a in all_links) else 0
            features['Links_in_tags'] = len(soup.find_all(['meta', 'script', 'link']))
            features['SFH'] = 1 if soup.find('form', action="/") else 0
            features['Iframe'] = 1 if soup.find('iframe') else 0

        except Exception as e:
            # 크롤링 실패 시 기본값
            print(f"⚠️  HTML crawling failed: {e}")
            for k in ['nb_hyperlinks', 'ratio_intHyperlinks', 'empty_title', 'domain_in_title',
                      'Favicon', 'URL_of_Anchor', 'Links_in_tags', 'SFH', 'Iframe']:
                features[k] = 0

        return features

    def _calculate_risk_score(self, features: Dict) -> Tuple[int, List[str]]:
        """URL 특징으로 위험도 점수 계산 (즉시 응답용)"""
        score = 0
        reasons = []

        # IP 주소 사용 (매우 위험)
        if features['ip'] == 1:
            score += 40
            reasons.append("IP 주소 사용")

        # 피싱 의심 키워드 (개수별 가중치)
        if features['phish_hints'] == 1:
            base_score = 30
            keyword_count = features.get('phish_hints_count', 1)
            additional_score = min((keyword_count - 1) * 10, 20)  # 최대 +20점
            score += base_score + additional_score
            if keyword_count > 1:
                reasons.append(f"피싱 의심 키워드 {keyword_count}개 포함")
            else:
                reasons.append("피싱 의심 키워드 포함")

        # 단축 URL (위험)
        if features.get('is_shortener') == 1:
            score += 25
            reasons.append("단축 URL 사용")

        # URL 길이
        if features['length_url'] > 150:
            score += 30
            reasons.append("매우 긴 URL 길이 (150자 초과)")
        elif features['length_url'] > 100:
            score += 20
            reasons.append("긴 URL 길이 (100자 초과)")

        # 도메인에 하이픈 포함
        if features['prefix_suffix'] == 1:
            score += 15
            reasons.append("도메인에 하이픈(-) 포함")

        # 의심스러운 TLD
        if features.get('suspicious_tld') == 1:
            score += 15
            reasons.append("의심스러운 도메인 확장자 (.xyz, .top, .club 등)")

        # 과도한 점 문자
        if features['nb_dots'] > 4:
            score += 15
            reasons.append("과도한 '.' 문자")

        # URL에 숫자 비율 높음
        if features['ratio_digits_url'] > 0.3:
            score += 15
            reasons.append("URL에 숫자 비율 높음")

        # 숫자 서브도메인
        if features.get('numeric_subdomain') == 1:
            score += 20
            reasons.append("숫자로만 된 서브도메인")

        # 호스트에 매우 짧은 단어
        if features['shortest_word_host'] < 3:
            score += 10
            reasons.append("호스트에 매우 짧은 단어")

        # 복합 위험 보너스 (여러 의심 요소가 겹칠 때)
        if len(reasons) >= 5:
            score += 25
            reasons.append("복합 위험 요소 다수 탐지")
        elif len(reasons) >= 3:
            score += 15
            reasons.append("복합 위험 요소 탐지")

        # 위험도 레벨 (0: 안전, 1: 의심, 2: 경고, 3: 위험)
        if score >= 70:
            level = 3
        elif score >= 50:
            level = 2
        elif score >= 30:
            level = 1
        else:
            level = 0

        return level, score, reasons

    def detect_immediate(self, url: str) -> Dict:
        """
        즉시 응답 - URL 특징 기반 탐지 (크롤링 없이 빠르게)

        Args:
            url: 분석할 URL

        Returns:
            {
                'level': int (0: 안전, 1: 의심, 2: 경고, 3: 위험),
                'score': float (0~100),
                'reasons': List[str],
                'method': 'url_based'
            }
        """
        if not url or len(url.strip()) < 10:
            return {
                'level': 0,
                'score': 0,
                'reasons': [],
                'method': 'url_based'
            }

        # URL 특징 추출
        url_features, domain = self._extract_url_features(url)

        # 위험도 계산
        level, score, reasons = self._calculate_risk_score(url_features)

        return {
            'level': level,
            'score': score,
            'reasons': reasons,
            'method': 'url_based',
            'domain': domain
        }

    def detect_comprehensive(self, url: str) -> Dict:
        """
        종합 분석 - PhishTank DB + ML 모델 (HTML 크롤링 포함)

        Args:
            url: 분석할 URL

        Returns:
            {
                'is_phishing': bool,
                'confidence': float,
                'source': str ('phishtank' or 'ml_model'),
                'method': 'comprehensive',
                'analyzed_url': str
            }
        """
        if not url or len(url.strip()) < 10:
            return {
                'is_phishing': False,
                'confidence': 0.0,
                'source': 'none',
                'method': 'comprehensive',
                'analyzed_url': url
            }

        # 1. PhishTank DB 체크 (확실한 피싱 사이트)
        if url in self.phishtank_db:
            return {
                'is_phishing': True,
                'confidence': 1.0,
                'source': 'phishtank',
                'method': 'comprehensive',
                'analyzed_url': url
            }

        # 2. ML 모델로 예측
        try:
            # URL 특징 추출
            url_features, domain = self._extract_url_features(url)

            # HTML 특징 추출 (크롤링)
            html_features = self._extract_html_features(url, domain)

            # 모든 특징 합치기
            features = {**url_features, **html_features}

            # 누락된 특징 보완
            for col in FEATURE_NAMES:
                if col not in features:
                    features[col] = 0

            # 고정 특징 (WHOIS 등 - 사용 안 함)
            features['domain_age'] = 0
            features['page_rank'] = 0
            features['google_index'] = 0
            features['Request_URL'] = 0
            features['empty_title.1'] = 0
            features['nb_hyperlinks.1'] = 0
            features['ratio_intHyperlinks.1'] = 0

            # DataFrame 생성
            features_df = pd.DataFrame([features])[FEATURE_NAMES]

            # 모델 추론
            scaled_array = self.scaler.transform(features_df)
            scaled_features = pd.DataFrame(scaled_array, columns=features_df.columns)
            raw_prob = self.model.predict_proba(scaled_features)[0][1]

            # 점수 보정 (Wave_to_WWW 방식)
            row = features_df.iloc[0]
            boost = 0

            # 피싱 보정
            if row['phish_hints'] == 1: boost += 0.10
            if row['prefix_suffix'] == 1: boost += 0.06
            if row['Favicon'] == 1: boost += 0.05
            if row['shortest_word_host'] <= 2: boost += 0.04
            if row['longest_words_raw'] > 20: boost += 0.03
            if row['ratio_digits_url'] > 0.3: boost += 0.03
            if row['nb_hyperlinks'] < 5: boost += 0.03
            if row['ratio_intHyperlinks'] < 0.3: boost += 0.02

            # 정상 보정
            if row['ratio_intHyperlinks'] > 0.6: boost -= 0.04
            if row['domain_in_title'] == 1: boost -= 0.02
            if row.get('Iframe', 1) == 0: boost -= 0.01
            if row['nb_hyperlinks'] > 20: boost -= 0.03

            # 신뢰 도메인 완화
            trusted_domains = ['google', 'netflix', 'naver', 'amazon', 'microsoft', 'akamai', 'apple']
            if any(t in domain for t in trusted_domains):
                boost -= 0.04

            # 제한 조정
            boost = min(max(boost, -0.08), 0.25)
            prob = min(max(raw_prob + boost, 0.0), 1.0)

            # 피싱 여부 판단 (threshold: 0.7)
            is_phishing = bool(prob >= 0.7)

            return {
                'is_phishing': is_phishing,
                'confidence': float(prob),
                'source': 'ml_model',
                'method': 'comprehensive',
                'analyzed_url': url
            }

        except Exception as e:
            print(f"❌ ML prediction failed: {e}")
            return {
                'is_phishing': False,
                'confidence': 0.0,
                'source': 'error',
                'method': 'comprehensive',
                'analyzed_url': url,
                'error': str(e)
            }


# 전역 인스턴스 (한 번만 로드)
_detector = None

def get_detector() -> PhishingSiteDetector:
    """피싱 사이트 탐지기 싱글톤 인스턴스 반환"""
    global _detector
    if _detector is None:
        _detector = PhishingSiteDetector()
    return _detector
