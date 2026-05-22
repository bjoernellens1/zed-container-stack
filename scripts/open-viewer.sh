#!/usr/bin/env bash
set -euo pipefail
./scripts/gui-allow.sh
${COMPOSE:-docker compose} --profile nvidia-sdk run --rm zed-nvidia-sdk bash -lc '/usr/local/zed/tools/ZED_Explorer'
