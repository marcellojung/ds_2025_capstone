---

### 8. **db/schema.sql**
```sql
-- PostgreSQL schema
CREATE TABLE IF NOT EXISTS ncs_category (
  code         VARCHAR(10) PRIMARY KEY,
  name         TEXT NOT NULL,
  level        INT NOT NULL CHECK (level BETWEEN 1 AND 4),
  parent_code  VARCHAR(10) REFERENCES ncs_category(code)
);

CREATE TABLE IF NOT EXISTS job_post (
  job_id            BIGINT PRIMARY KEY,
  job_title         TEXT NOT NULL,
  job_link          TEXT NOT NULL,
  company           TEXT,
  work_place        TEXT,
  career            TEXT,
  education         TEXT,
  sectors           JSONB,
  last_modified_at  TIMESTAMPTZ,
  deadline_at       TIMESTAMPTZ,
  start_raw         TEXT,
  deadline_raw      TEXT,
  first_seen_at     TIMESTAMPTZ DEFAULT now(),
  last_seen_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_job_post_last_modified  ON job_post(last_modified_at DESC);
CREATE INDEX IF NOT EXISTS idx_job_post_deadline       ON job_post(deadline_at);
CREATE INDEX IF NOT EXISTS idx_job_post_company        ON job_post(company);
CREATE INDEX IF NOT EXISTS idx_job_post_sectors_gin    ON job_post USING GIN (sectors jsonb_path_ops);

CREATE TABLE IF NOT EXISTS job_ncs_map (
  job_id           BIGINT REFERENCES job_post(job_id) ON DELETE CASCADE,
  ncs_code         VARCHAR(10),
  level            INT CHECK (level BETWEEN 1 AND 4),
  score            REAL,
  decided          BOOLEAN DEFAULT FALSE,
  model_version    TEXT,
  taxonomy_version TEXT,
  created_at       TIMESTAMPTZ DEFAULT now(),
  PRIMARY KEY(job_id, ncs_code, model_version)
);

CREATE INDEX IF NOT EXISTS idx_job_ncs_map_code ON job_ncs_map(ncs_code);

CREATE OR REPLACE VIEW v_job_post_recent_24h AS
SELECT *
FROM job_post
WHERE last_modified_at >= now() - INTERVAL '1 day';