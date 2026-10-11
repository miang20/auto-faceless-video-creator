#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

REPO_DIR="$HOME/v2-test/repo"
WORKER_DIR="$HOME/v2-test/worker"
WORKER_TARGET="$WORKER_DIR/github_worker.py"
SERVICE_DIR="${PREFIX:-$HOME/../usr}/var/service/faceless-worker"

if [ ! -d "$REPO_DIR/.git" ]; then
  echo "[V2 DEPLOY] Repository not found at $REPO_DIR"
  exit 1
fi

echo "[V2 DEPLOY] Syncing the latest V2 code from GitHub..."
git -C "$REPO_DIR" pull --ff-only origin main

echo "[V2 DEPLOY] Checking Python syntax before deployment..."
python -m compileall -q "$REPO_DIR/app.py" "$REPO_DIR/core" "$REPO_DIR/worker"

mkdir -p "$WORKER_DIR"
if [ -f "$WORKER_TARGET" ]; then
  backup="$WORKER_TARGET.backup.$(date +%Y%m%d-%H%M%S)"
  cp "$WORKER_TARGET" "$backup"
  echo "[V2 DEPLOY] Previous worker backed up."
fi

cp "$REPO_DIR/worker/github_worker.py" "$WORKER_TARGET"
chmod 700 "$WORKER_TARGET"
echo "[V2 DEPLOY] Updated local worker from the verified repository source."

if command -v sv >/dev/null 2>&1 && [ -d "$SERVICE_DIR" ]; then
  sv restart "$SERVICE_DIR"
  echo "[V2 DEPLOY] Worker service restarted."
else
  echo "[V2 DEPLOY] Code synced, but runit service was not found at $SERVICE_DIR."
  echo "[V2 DEPLOY] Worker restart must be done manually once."
fi

echo "[V2 DEPLOY] Deployment step finished. Open/refresh Auto Faceless Studio V2; Streamlit should reload app.py automatically."
