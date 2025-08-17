# NCS Saramin CSV Loader

이 프로젝트는 Saramin에서 수집된 **채용공고 CSV 파일을 PostgreSQL DB에 자동 적재**하는 환경을 제공합니다.  
매일 크론(cron)에 의해 실행되며, `job_id` 기준으로 중복을 제거하고 **최근 24시간 내 등록/수정된 공고**만 DB에 반영합니다.

---

## 📂 구성 파일

- `docker-compose.yml` : PostgreSQL + Loader(cron 포함) 서비스 정의
- `Dockerfile` : Python 3.11 + cron 환경
- `requirements.txt` : Python 의존성
- `load_csv.py` : CSV → DB 업서트 스크립트
- `entrypoint.sh` : 컨테이너 시작 시 1회 적재 후 cron 실행
- `cronjob` : 매일 03:05 KST 자동 실행 설정
- `db/schema.sql` : PostgreSQL 스키마 (초기 자동 적용)
- `data/saramin.csv` : 매일 수집되는 CSV 파일 (외부에서 마운트)

---

## 🚀 사용법

```bash
mkdir -p ncs_loader_project/data
cp your_daily.csv ncs_loader_project/data/saramin.csv

cd ncs_loader_project
docker compose up -d --build

docker logs -f ncs_loader
```
