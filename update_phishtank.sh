#!/bin/bash

# PhishTank 데이터베이스 자동 갱신 스크립트
# 매일 새벽 2시에 크론탭으로 실행됨

# 변수 설정
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA_DIR="${SCRIPT_DIR}/data/phishtank"
TEMP_DIR="${DATA_DIR}/temp"
PHISHTANK_URL="http://data.phishtank.com/data/online-valid.csv"
OUTPUT_FILE="${DATA_DIR}/phishing_urls.txt"
LOG_FILE="${DATA_DIR}/update.log"

# 로그 함수
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "${LOG_FILE}"
}

# 디렉토리 생성
mkdir -p "${DATA_DIR}"
mkdir -p "${TEMP_DIR}"

log "=== PhishTank DB 갱신 시작 ==="

# 1. PhishTank CSV 다운로드
log "PhishTank CSV 다운로드 중..."
if curl -L -o "${TEMP_DIR}/phishtank.csv" "${PHISHTANK_URL}"; then
    log "CSV 다운로드 완료"
else
    log "CSV 다운로드 실패"
    exit 1
fi

# 2. CSV에서 URL만 추출 (헤더 제외, 두 번째 컬럼)
log "URL 추출 중..."
if tail -n +2 "${TEMP_DIR}/phishtank.csv" | cut -d',' -f2 | sed 's/"//g' > "${TEMP_DIR}/phishing_urls_new.txt"; then
    URL_COUNT=$(wc -l < "${TEMP_DIR}/phishing_urls_new.txt" | tr -d ' ')
    log "URL 추출 완료 (${URL_COUNT}개)"
else
    log "URL 추출 실패"
    exit 1
fi

# 3. 빈 줄 제거 및 정렬
log "데이터 정리 중..."
grep -v '^[[:space:]]*$' "${TEMP_DIR}/phishing_urls_new.txt" | sort -u > "${TEMP_DIR}/phishing_urls_clean.txt"
CLEAN_COUNT=$(wc -l < "${TEMP_DIR}/phishing_urls_clean.txt" | tr -d ' ')
log "정리 완료 (중복 제거 후 ${CLEAN_COUNT}개)"

# 4. 기존 파일 백업
if [ -f "${OUTPUT_FILE}" ]; then
    BACKUP_FILE="${DATA_DIR}/phishing_urls_backup_$(date '+%Y%m%d_%H%M%S').txt"
    cp "${OUTPUT_FILE}" "${BACKUP_FILE}"
    log "기존 파일 백업: ${BACKUP_FILE}"
fi

# 5. 새 파일로 교체
mv "${TEMP_DIR}/phishing_urls_clean.txt" "${OUTPUT_FILE}"
log "PhishTank DB 갱신 완료: ${OUTPUT_FILE}"

# 6. 임시 파일 정리
rm -rf "${TEMP_DIR}"
log "임시 파일 정리 완료"

# 7. 최종 통계
log "=== 최종 통계 ==="
log "총 피싱 URL 개수: ${CLEAN_COUNT}"
log "파일 크기: $(du -h "${OUTPUT_FILE}" | cut -f1)"
log "=== PhishTank DB 갱신 종료 ==="

exit 0
