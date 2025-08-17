#!/bin/bash
set -euo pipefail
if [ -f "$CSV_PATH" ]; then
  echo "[entrypoint] Running initial load: $CSV_PATH" >&2
  python /app/load_csv.py --csv "$CSV_PATH" || true
else
  echo "[entrypoint] CSV not found at $CSV_PATH (initial run skipped)" >&2
fi

printenv | sed 's/\\(.*\\)/export \\1/g' > /etc/profile.d/00-container-env.sh

echo "[entrypoint] Starting cron..."
cron && tail -n+1 -f /var/log/cron.log