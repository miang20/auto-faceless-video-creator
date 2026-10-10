#!/data/data/com.termux/files/usr/bin/bash
set -Eeuo pipefail

REPO_DIR="$HOME/v2-test/repo"
JOB_ID="v2_63eb8c9550c3"
SERVICE="faceless-worker"
TOKEN_FILE="$PREFIX/var/service/af-v2-worker/env/GITHUB_TOKEN"
BACKUP_DIR="$HOME/v2-test/pre-sync-backup/drawtext-recovery-$(date +%Y%m%d-%H%M%S)"

cd "$REPO_DIR"
mkdir -p "$BACKUP_DIR"

for file in core/job_runner.py core/video_processor.py; do
  if [ -f "$file" ]; then
    cp -p "$file" "$BACKUP_DIR/$(basename "$file")"
  fi
done

echo "[1/5] Fetching latest GitHub code..."
git fetch origin main
git show origin/main:core/job_runner.py > core/job_runner.py
git show origin/main:core/video_processor.py > core/video_processor.py

echo "[2/5] Checking Python syntax..."
python -m py_compile core/job_runner.py core/video_processor.py

echo "[3/5] Restarting worker..."
sv restart "$SERVICE"

echo "[4/5] Re-queueing the failed job on GitHub..."
python - "$JOB_ID" "$TOKEN_FILE" <<'PY'
import base64
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

job_id, token_file = sys.argv[1], Path(sys.argv[2])
token = os.environ.get("GITHUB_TOKEN", "").strip()
if not token and token_file.is_file():
    token = token_file.read_text(encoding="utf-8").strip()
if not token:
    raise SystemExit("STOP: GitHub token not found; no job was re-queued.")

api = f"https://api.github.com/repos/miang20/auto-faceless-video-creator/contents/jobs/{job_id}.json"
headers = {
    "Authorization": f"Bearer {token}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "Content-Type": "application/json",
}
request = urllib.request.Request(api, headers=headers)
try:
    with urllib.request.urlopen(request, timeout=30) as response:
        current = json.load(response)
except urllib.error.HTTPError as exc:
    raise SystemExit(f"STOP: Cannot read GitHub job ({exc.code}); job was not re-queued.")

raw = base64.b64decode(current["content"]).decode("utf-8")
job = json.loads(raw)
job["status"] = "queued"
job["error"] = None
job.pop("result_path", None)
job["updated_at"] = datetime.now(timezone.utc).isoformat()
encoded = base64.b64encode((json.dumps(job, indent=2, ensure_ascii=False) + "\n").encode("utf-8")).decode("ascii")
payload = json.dumps({
    "message": f"Re-queue {job_id} after FFmpeg caption recovery",
    "content": encoded,
    "sha": current["sha"],
}).encode("utf-8")
request = urllib.request.Request(api, data=payload, headers=headers, method="PUT")
try:
    with urllib.request.urlopen(request, timeout=30) as response:
        if response.status not in (200, 201):
            raise SystemExit(f"STOP: GitHub returned HTTP {response.status}.")
except urllib.error.HTTPError as exc:
    body = exc.read().decode("utf-8", "replace")
    raise SystemExit(f"STOP: GitHub could not re-queue the job ({exc.code}): {body[:300]}")

# Keep the local repo job record aligned with the queued GitHub record.
local_job = Path("jobs") / f"{job_id}.json"
local_job.parent.mkdir(parents=True, exist_ok=True)
local_job.write_text(json.dumps(job, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(f"Queued {job_id}. Worker will pick it up on its next poll.")
PY

echo "[5/5] Recovery prepared."
echo "Backup: $BACKUP_DIR"
echo "Downloader was not modified."
echo "Check the app's V2 Jobs panel for completed status and the MP4 in:"
echo "$HOME/storage/shared/Movies/AutoFaceless/"
