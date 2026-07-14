#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if ! command -v docker-compose >/dev/null; then
  echo "docker-compose is not installed; there is nothing to clean through this project." >&2
  exit 0
fi

cd "$PROJECT_ROOT"
docker-compose down --volumes --remove-orphans

# Remove only images tagged for this project; other server images are untouched.
image_ids="$(docker images -q pdm-frontend pdm-backend 2>/dev/null | sort -u)"
if [[ -n "$image_ids" ]]; then
  docker rmi "$image_ids"
fi
