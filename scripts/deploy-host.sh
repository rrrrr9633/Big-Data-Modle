#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$PROJECT_ROOT/backend"
SERVICE_USER="${SERVICE_USER:-pdm}"
SERVICE_FILE="/etc/systemd/system/pdm-backend.service"

if ! command -v nginx >/dev/null; then
  echo "nginx is required. Install and configure it before running this script." >&2
  exit 1
fi

if ! command -v mysql >/dev/null; then
  echo "MySQL client is required. Install and initialize MySQL before running this script." >&2
  exit 1
fi

if ! command -v redis-server >/dev/null; then
  echo "Redis is required by the application. Install redis-server before running this script." >&2
  exit 1
fi

if ! id -u "$SERVICE_USER" >/dev/null 2>&1; then
  sudo useradd --system --home "$BACKEND_DIR" --shell /usr/sbin/nologin "$SERVICE_USER"
fi

python3 -m venv "$BACKEND_DIR/.venv"
"$BACKEND_DIR/.venv/bin/pip" install --upgrade pip
"$BACKEND_DIR/.venv/bin/pip" install -r "$BACKEND_DIR/requirements.prod.txt"

sudo chown -R "$SERVICE_USER:$SERVICE_USER" "$BACKEND_DIR"
sudo install -m 0644 "$PROJECT_ROOT/deploy/systemd/pdm-backend.service" "$SERVICE_FILE"
sudo systemctl daemon-reload
sudo systemctl enable --now pdm-backend.service
sudo systemctl restart nginx
sudo systemctl --no-pager --full status pdm-backend.service
