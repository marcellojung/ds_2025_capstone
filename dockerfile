# CSV → Postgres 로더 + cron
FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    cron tzdata libpq5 gcc build-essential \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 앱 소스
COPY load_csv.py /app/load_csv.py
COPY entrypoint.sh /entrypoint.sh
COPY cronjob /etc/cron.d/loader-cron

# cron 권한 및 로그 준비
RUN chmod 0644 /etc/cron.d/loader-cron \
    && touch /var/log/cron.log \
    && chmod +x /entrypoint.sh

# 환경변수 (docker-compose에서 덮어쓰기 권장)
ENV PGHOST=postgres \
    PGPORT=5432 \
    PGDATABASE=jobs \
    PGUSER=jobs_loader \
    PGPASSWORD=changeme \
    CSV_PATH=/data/saramin.csv \
    TZ=Asia/Seoul

# 컨테이너 시작 시: 1) 즉시 한 번 실행 → 2) cron 포그라운드
CMD ["/entrypoint.sh"]