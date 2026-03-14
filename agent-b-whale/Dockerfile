# ──────────────────────────────────────────────
# Dockerfile — Railway 배포용
# ──────────────────────────────────────────────
# Railway에 이 프로젝트를 올리면, 이 파일을 읽고 자동으로
# Python 환경을 만들어서 에이전트 B를 실행해줌.
#
# 쉽게 말하면: "이 앱을 실행하려면 이런 환경이 필요해" 라는 레시피.
# ──────────────────────────────────────────────

# Python 3.11 사용 (slim = 가벼운 버전)
FROM python:3.11-slim

# 작업 디렉토리 설정
WORKDIR /app

# 패키지 목록 먼저 복사 (캐시 효율)
# → requirements.txt가 안 바뀌면 패키지 재설치 안 함 (빠름)
COPY requirements.txt .

# Python 패키지 설치
RUN pip install --no-cache-dir -r requirements.txt

# 소스코드 전체 복사
COPY . .

# 에이전트 B 실행
CMD ["python", "main.py"]
