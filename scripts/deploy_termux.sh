#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

REPO_DIR="$HOME/v2-test/repo"
WORKER_DIR="$HOME/v2-test/worker"
WORKER_TARGET="$WORKER_DIR/github_worker.py"
SERVICE_DIR="${PREFIX:-$HOME/../usr}/var/service/faceless-worker"
ALT_SERVICE_DIR="${PREFIX:-$HOME/../usr}/var/service/af-v2-worker"
BACKUP_ROOT="$HOME/v2-deploy-backups"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP_DIR="$BACKUP_ROOT/$STAMP"
SERVICE_READY=0

if [ ! -d "$REPO_DIR/.git" ]; then
  echo "[V2 DEPLOY] Repository not found at $REPO_DIR"
  exit 1
fi

# Local job JSON files are runtime state, not source code. Preserve dirty
# tracked job files outside the repository before syncing so git pull cannot
# be blocked by a worker/app-updated job record.
mapfile -t DIRTY_JOB_PATHS < <(
  {
    git -C "$REPO_DIR" diff --name-only -- jobs/
    git -C "$REPO_DIR" diff --cached --name-only -- jobs/
  } | sort -u
)

if [ "${#DIRTY_JOB_PATHS[@]}" -gt 0 ]; then
  mkdir -p "$BACKUP_DIR"
  for relative_path in "${DIRTY_JOB_PATHS[@]}"; do
    if [ -f "$REPO_DIR/$relative_path" ]; then
      mkdir -p "$BACKUP_DIR/$(dirname "$relative_path")"
      cp -p "$REPO_DIR/$relative_path" "$BACKUP_DIR/$relative_path"
      echo "[V2 DEPLOY] Preserved local runtime file: $BACKUP_DIR/$relative_path"
    fi
  done
  git -C "$REPO_DIR" restore --source=HEAD --staged --worktree -- jobs/
fi

echo "[V2 DEPLOY] Syncing the latest V2 code from GitHub..."
git -C "$REPO_DIR" pull --ff-only origin main

echo "[V2 DEPLOY] Checking Python syntax before deployment..."
python -m compileall -q "$REPO_DIR/app.py" "$REPO_DIR/core" "$REPO_DIR/worker"

mkdir -p "$WORKER_DIR"
if [ -f "$WORKER_TARGET" ]; then
  cp -p "$WORKER_TARGET" "$WORKER_TARGET.backup.$STAMP"
  echo "[V2 DEPLOY] Previous worker backed up."
fi

cp "$REPO_DIR/worker/github_worker.py" "$WORKER_TARGET"
chmod 700 "$WORKER_TARGET"
echo "[V2 DEPLOY] Updated local worker from the repository source."

if command -v sv >/dev/null 2>&1 && [ -d "$SERVICE_DIR" ]; then
  # "restart" can leave a runit service down when its persistent down flag
  # is present. "up" explicitly clears that state and starts the service.
  echo "[V2 DEPLOY] Bringing the worker service up..."
  sv up "$SERVICE_DIR" || true
  sleep 3
  if sv status "$SERVICE_DIR" 2>&1 | grep -q '^run:'; then
    echo "[V2 DEPLOY] Worker service is running."
    SERVICE_READY=1
  else
    echo "[V2 DEPLOY] Worker did not enter running state. Checking alternate service name..."
    ALT_SERVICE_DIR="${PREFIX:-$HOME/../usr}/var/service/af-v2-worker"
    if [ -d "$ALT_SERVICE_DIR" ]; then
      sv up "$ALT_SERVICE_DIR" || true
      sleep 3
      if sv status "$ALT_SERVICE_DIR" 2>&1 | grep -q '^run:'; then
        echo "[V2 DEPLOY] Alternate worker service is running: $ALT_SERVICE_DIR"
        SERVICE_READY=1
      else
        echo "[V2 DEPLOY] Neither worker service confirmed running."
        sv status "$SERVICE_DIR" 2>&1 || true
        sv status "$ALT_SERVICE_DIR" 2>&1 || true
      fi
    else
      sv status "$SERVICE_DIR" 2>&1 || true
    fi
  fi
else
  echo "[V2 DEPLOY] Code synced, but runit service was not found at $SERVICE_DIR."
  echo "[V2 DEPLOY] Worker restart was not attempted."
fi

# Enforce one worker owner: prefer faceless-worker, otherwise keep af-v2-worker.
if [ "$SERVICE_READY" -eq 1 ]; then
  if [ -d "$SERVICE_DIR" ] && sv status "$SERVICE_DIR" 2>&1 | grep -q '^run:'; then
    if [ -d "$ALT_SERVICE_DIR" ]; then
      sv down "$ALT_SERVICE_DIR" >/dev/null 2>&1 || true
      echo "[V2 DEPLOY] Disabled duplicate worker service: $ALT_SERVICE_DIR"
    fi
  elif [ -d "$ALT_SERVICE_DIR" ] && sv status "$ALT_SERVICE_DIR" 2>&1 | grep -q '^run:'; then
    if [ -d "$SERVICE_DIR" ]; then
      sv down "$SERVICE_DIR" >/dev/null 2>&1 || true
      echo "[V2 DEPLOY] Disabled duplicate worker service: $SERVICE_DIR"
    fi
  fi
fi

# Automatically retry the previously blocked Whisper test only after the worker
# is confirmed running. This avoids asking the user to manually create a job.
if [ "$SERVICE_READY" -eq 1 ]; then
  TOKEN_FILE="${PREFIX:-$HOME/../usr}/var/service/af-v2-worker/env/GITHUB_TOKEN"
  if [ -s "$TOKEN_FILE" ]; then
    python - "$TOKEN_FILE" "$REPO_DIR" <<'PY'
import base64
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

token_file, repo_dir = Path(sys.argv[1]), Path(sys.argv[2])
token = token_file.read_text(encoding="utf-8").strip()
if not token:
    print("[V2 DEPLOY] GitHub token file is empty; automatic test retry skipped.")
    raise SystemExit(0)

job_id = "v2_6c3f1b9e8a21"
api = f"https://api.github.com/repos/miang20/auto-faceless-video-creator/contents/jobs/{job_id}.json"
headers = {
    "Authorization": f"Bearer {token}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "Content-Type": "application/json",
}
request = urllib.request.Request(api + "?ref=main", headers=headers)
try:
    with urllib.request.urlopen(request, timeout=25) as response:
        current = json.load(response)
except Exception as exc:
    print(f"[V2 DEPLOY] Could not read the saved test job; skipped: {exc}")
    raise SystemExit(0)

try:
    job = json.loads(base64.b64decode(current["content"]).decode("utf-8"))
except Exception as exc:
    print(f"[V2 DEPLOY] Saved test job was unreadable; skipped: {exc}")
    raise SystemExit(0)

# This script only targets the single known V2 test job. Retry it whenever
# it is failed, because its error text can vary across Whisper/runtime versions.
if job.get("job_id") != job_id or job.get("status") != "failed":
    print(f"[V2 DEPLOY] Saved test job is not failed (status={job.get('status')}); left unchanged.")
    raise SystemExit(0)

job["status"] = "queued"
job["error"] = None
job["updated_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
payload = {
    "message": f"Retry V2 test job {job_id} after worker startup and Whisper fixes",
    "content": base64.b64encode((json.dumps(job, indent=2, ensure_ascii=False) + "\n").encode("utf-8")).decode("ascii"),
    "sha": current["sha"],
    "branch": "main",
}
request = urllib.request.Request(api, data=json.dumps(payload).encode("utf-8"), headers=headers, method="PUT")
try:
    with urllib.request.urlopen(request, timeout=25) as response:
        if response.status not in (200, 201):
            raise RuntimeError(f"GitHub returned HTTP {response.status}")
    local = repo_dir / "jobs" / f"{job_id}.json"
    local.write_text(json.dumps(job, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"[V2 DEPLOY] Automatically re-queued test job {job_id}; worker will pick it up.")
except Exception as exc:
    print(f"[V2 DEPLOY] Could not re-queue test job automatically: {exc}")
PY
  else
    echo "[V2 DEPLOY] Worker is running, but token file was not found; automatic test retry skipped."
  fi
else
  echo "[V2 DEPLOY] Worker is not confirmed running; saved test job was left untouched."
fi

echo "[V2 DEPLOY] Deployment step finished. Refresh Auto Faceless Studio V2."
