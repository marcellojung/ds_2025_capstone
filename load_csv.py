#!/usr/bin/env python3
import os, argparse, json, re
from datetime import datetime, timedelta
from dateutil import tz
import pandas as pd
from sqlalchemy import create_engine, text

KST = tz.gettz("Asia/Seoul")

REL_REGEX = re.compile(r"(?P<num>\d+)\s*(?P<unit>분|시간|일)\s*전\s*(등록|수정)?")
ABS_DEADLINE = re.compile(r"~\s*(?P<mm>\d{2})\.(?P<dd>\d{2})")  # 예: ~08.25(월)

def parse_relative(text: str):
    if not isinstance(text, str):
        return None
    m = REL_REGEX.search(text)
    if not m:
        return None
    num = int(m.group("num"))
    unit = m.group("unit")
    now = datetime.now(tz=KST)
    if unit == "분":
        return now - timedelta(minutes=num)
    if unit == "시간":
        return now - timedelta(hours=num)
    if unit == "일":
        return now - timedelta(days=num)
    return None

def parse_deadline(text: str):
    """ '~08.25(월)' 형태를 올해 날짜로 파싱 """
    if not isinstance(text, str):
        return None
    m = ABS_DEADLINE.search(text)
    if not m:
        return None
    mm = int(m.group("mm"))
    dd = int(m.group("dd"))
    year = datetime.now(tz=KST).year
    try:
        return datetime(year, mm, dd, tzinfo=KST)
    except Exception:
        return None

def to_list(val):
    if isinstance(val, list):
        return val
    if isinstance(val, str):
        s = val.strip()
        try:
            j = s.replace("'", '"')
            v = json.loads(j)
            return v if isinstance(v, list) else [str(v)]
        except Exception:
            return [s]
    return []

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True, help="수집된 Saramin CSV 경로")
    args = ap.parse_args()

    df = pd.read_csv(args.csv, sep=",")
    rename_map = {
        "job_id":"job_id",
        "job_title":"job_title",
        "job_link":"job_link",
        "job_sector":"job_sector",
        "comp_name":"company",
        "work_place":"work_place",
        "career":"career",
        "education":"education",
        "start_date":"start_text",
        "deadline":"deadline_text",
    }
    df = df.rename(columns=rename_map)

    required = ["job_id","job_title","job_link","company","work_place","career","education","start_text","deadline_text","job_sector"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise SystemExit(f"CSV에 필수 컬럼 누락: {missing}")

    df["_parsed_rel"] = df["deadline_text"].apply(parse_relative)
    df.loc[df["_parsed_rel"].isna(), "_parsed_rel"] = df["start_text"].apply(parse_relative)
    df["_deadline_abs"] = df["start_text"].apply(parse_deadline)

    df = df.sort_values(by=["job_id","_parsed_rel"], ascending=[True, False])
    df = df.drop_duplicates(subset=["job_id"], keep="first")

    cutoff = datetime.now(tz=KST) - timedelta(days=1)
    df = df[df["_parsed_rel"].notna() & (df["_parsed_rel"] >= cutoff)]

    df["sectors"] = df["job_sector"].apply(to_list)

    user = os.getenv("PGUSER"); pwd = os.getenv("PGPASSWORD")
    host = os.getenv("PGHOST", "localhost"); port = int(os.getenv("PGPORT", "5432")); db = os.getenv("PGDATABASE", "jobs")
    engine = create_engine(f"postgresql+psycopg2://{user}:{pwd}@{host}:{port}/{db}")

    with engine.begin() as conn:
        rows = []
        for _, r in df.iterrows():
            rows.append({
                "job_id": int(r["job_id"]),
                "job_title": str(r["job_title"]),
                "job_link": str(r["job_link"]),
                "company": None if pd.isna(r["company"]) else str(r["company"]),
                "work_place": None if pd.isna(r["work_place"]) else str(r["work_place"]),
                "career": None if pd.isna(r["career"]) else str(r["career"]),
                "education": None if pd.isna(r["education"]) else str(r["education"]),
                "sectors": json.dumps(r["sectors"], ensure_ascii=False),
                "last_modified_at": r["_parsed_rel"],
                "deadline_at": r["_deadline_abs"],
                "start_raw": None if pd.isna(r["start_text"]) else str(r["start_text"]),
                "deadline_raw": None if pd.isna(r["deadline_text"]) else str(r["deadline_text"]),
            })
        if rows:
            conn.exec_driver_sql("CREATE TEMP TABLE IF NOT EXISTS job_post_stage (LIKE job_post INCLUDING ALL) ON COMMIT DROP;")
            cols = ["job_id","job_title","job_link","company","work_place","career","education","sectors","last_modified_at","deadline_at","start_raw","deadline_raw"]
            values_sql = ",".join(["(" + ",".join(["%s"]*len(cols)) + ")"] * len(rows))
            flat = []
            for r in rows:
                flat.extend([r[c] for c in cols])
            conn.exec_driver_sql(f"INSERT INTO job_post_stage ({','.join(cols)}) VALUES {values_sql}", flat)

            conn.execute(text("""
                INSERT INTO job_post AS t (job_id, job_title, job_link, company, work_place, career, education,
                                           sectors, last_modified_at, deadline_at, start_raw, deadline_raw,
                                           first_seen_at, last_seen_at)
                SELECT job_id, job_title, job_link, company, work_place, career, education,
                       sectors::jsonb, last_modified_at, deadline_at, start_raw, deadline_raw,
                       now(), now()
                FROM job_post_stage
                ON CONFLICT (job_id) DO UPDATE
                  SET job_title = EXCLUDED.job_title,
                      job_link = EXCLUDED.job_link,
                      company = EXCLUDED.company,
                      work_place = EXCLUDED.work_place,
                      career = EXCLUDED.career,
                      education = EXCLUDED.education,
                      sectors = EXCLUDED.sectors,
                      deadline_at = COALESCE(EXCLUDED.deadline_at, job_post.deadline_at),
                      start_raw = EXCLUDED.start_raw,
                      deadline_raw = EXCLUDED.deadline_raw,
                      last_seen_at = now(),
                      last_modified_at = CASE
                          WHEN job_post.last_modified_at IS NULL THEN EXCLUDED.last_modified_at
                          WHEN EXCLUDED.last_modified_at IS NULL THEN job_post.last_modified_at
                          WHEN EXCLUDED.last_modified_at >= job_post.last_modified_at THEN EXCLUDED.last_modified_at
                          ELSE job_post.last_modified_at
                      END;
            """))
        print(f"[load_csv] Upserted rows: {len(rows)}")
if __name__ == "__main__":
    main()