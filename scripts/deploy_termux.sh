#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

REPO_DIR="$HOME/v2-test/repo"
WORKER_DIR="$HOME/v2-test/worker"
WORKER_TARGET="$WORKER_DIR/github_worker.py"
SERVICE_DIR="${PREFIX:-$HOME/../usr}/var/service/faceless-worker"
BACKUP_ROOT="$HOME/v2-deploy-backups"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP_DIR="$BACKUP_ROOT/$STAMP"

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
  sv restart "$SERVICE_DIR"
  echo "[V2 DEPLOY] Worker service restarted."
else
  echo "[V2 DEPLOY] Code synced, but runit service was not found at $SERVICE_DIR."
  echo "[V2 DEPLOY] Worker restart was not attempted."
fi

echo "[V2 DEPLOY] Deployment step finished. Refresh Auto Faceless Studio V2."
