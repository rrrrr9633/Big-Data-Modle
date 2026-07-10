#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FRONTEND_DIR="$PROJECT_ROOT/frontend"
NGINX_WEB_ROOT="${NGINX_WEB_ROOT:-/var/www/tianxiadiyi.xyz}"

npm --prefix "$FRONTEND_DIR" run build
sudo install -d "$NGINX_WEB_ROOT"
sudo rsync -a --delete "$FRONTEND_DIR/dist/" "$NGINX_WEB_ROOT/"
sudo nginx -t
sudo systemctl reload nginx