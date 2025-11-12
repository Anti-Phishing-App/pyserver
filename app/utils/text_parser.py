"""
텍스트 파싱 유틸리티

SMS 메시지에서 URL을 추출하고 텍스트를 정리하는 기능을 제공합니다.
"""
import re
from typing import Tuple, List


def extract_urls(text: str) -> List[str]:
    """
    텍스트에서 URL을 추출합니다.

    Args:
        text: URL이 포함된 텍스트

    Returns:
        추출된 URL 목록

    Examples:
        >>> extract_urls("택배 도착 http://example.com 확인하세요")
        ['http://example.com']
        >>> extract_urls("링크: https://test.com 또는 http://sample.kr")
        ['https://test.com', 'http://sample.kr']
    """
    # URL 정규표현식 패턴
    # http://, https://, www. 로 시작하는 URL 매칭
    url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
    www_pattern = r'www\.[^\s<>"{}|\\^`\[\]]+'

    urls = []

    # http://, https:// URL 추출
    http_urls = re.findall(url_pattern, text, re.IGNORECASE)
    urls.extend(http_urls)

    # www. URL 추출 (http가 없는 경우)
    www_urls = re.findall(www_pattern, text, re.IGNORECASE)
    # www URL은 http://를 붙여줌
    for www_url in www_urls:
        if not any(www_url in url for url in urls):  # 중복 제거
            urls.append(f"http://{www_url}")

    # 단축 URL 패턴 (bit.ly, goo.gl 등)
    short_url_pattern = r'(?:bit\.ly|goo\.gl|t\.co|tinyurl\.com|ow\.ly|is\.gd)/[^\s<>"{}|\\^`\[\]]+'
    short_urls = re.findall(short_url_pattern, text, re.IGNORECASE)
    for short_url in short_urls:
        if not any(short_url in url for url in urls):
            urls.append(f"http://{short_url}")

    # 중복 제거 및 정렬
    return list(dict.fromkeys(urls))  # 순서 유지하며 중복 제거


def remove_urls(text: str) -> str:
    """
    텍스트에서 URL을 제거합니다.

    Args:
        text: URL이 포함된 텍스트

    Returns:
        URL이 제거된 텍스트

    Examples:
        >>> remove_urls("택배 도착 http://example.com 확인하세요")
        '택배 도착  확인하세요'
    """
    # URL 패턴들
    patterns = [
        r'https?://[^\s<>"{}|\\^`\[\]]+',  # http://, https://
        r'www\.[^\s<>"{}|\\^`\[\]]+',  # www.
        r'(?:bit\.ly|goo\.gl|t\.co|tinyurl\.com|ow\.ly|is\.gd)/[^\s<>"{}|\\^`\[\]]+',  # 단축 URL
    ]

    cleaned_text = text
    for pattern in patterns:
        cleaned_text = re.sub(pattern, '', cleaned_text, flags=re.IGNORECASE)

    # 연속된 공백을 하나로 정리
    cleaned_text = re.sub(r'\s+', ' ', cleaned_text)

    return cleaned_text.strip()


def parse_sms_message(message: str) -> Tuple[str, List[str]]:
    """
    SMS 메시지를 파싱하여 텍스트와 URL을 분리합니다.

    Args:
        message: SMS 전체 메시지

    Returns:
        (텍스트, URL 목록) 튜플
        - 텍스트: URL이 제거된 순수 텍스트
        - URL 목록: 추출된 URL들

    Examples:
        >>> parse_sms_message("택배 도착 http://example.com 확인하세요")
        ('택배 도착 확인하세요', ['http://example.com'])
    """
    urls = extract_urls(message)
    text = remove_urls(message)

    return text, urls
