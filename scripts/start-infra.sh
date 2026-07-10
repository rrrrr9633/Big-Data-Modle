#!/usr/bin/env bash
set -euo pipefail

docker compose up -d mysql redis timescaledb kafka emqx