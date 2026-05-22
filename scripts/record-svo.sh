#!/usr/bin/env bash
set -euo pipefail
SESSION=${1:-$(date +%Y%m%d_%H%M%S)}
${COMPOSE:-docker compose} --profile nvidia-sdk run --rm zed-nvidia-sdk bash -lc "python3 /workspace/tools/zed_record_svo.py --out /data/svo/${SESSION}.svo2 --duration \"\${ZED_RECORD_SECONDS:-0}\" --resolution \"\${ZED_RESOLUTION:-HD720}\" --fps \"\${ZED_FPS:-30}\" --depth-mode \"\${ZED_DEPTH_MODE:-NEURAL_LIGHT}\""
