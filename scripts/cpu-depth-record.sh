#!/usr/bin/env bash
# Record ZED 2 depth + RGB on CPU/Intel/AMD (no NVIDIA required).
# Runs inside the opencapture container; do not call directly on the host.
#
# Usage (from host):
#   make cpu-capture [SESSION=myrun]
#   make intel-capture [SESSION=myrun]
#
# Usage (inside container):
#   /workspace/scripts/cpu-depth-record.sh [SESSION_NAME] [extra args...]

set -euo pipefail

SESSION="${1:-$(date +%Y%m%d_%H%M%S)}"
shift || true   # remaining args forwarded to recorder

OUT_DIR="/data/rgbd/${SESSION}"

exec zed_oc_depth_recorder \
    --out "${OUT_DIR}" \
    --fps  "${ZED_FPS:-30}" \
    --resolution "${ZED_RESOLUTION:-HD720}" \
    --num-disp "${ZED_OC_SGBM_NUM_DISP:-128}" \
    --block-size "${ZED_OC_SGBM_BLOCK_SIZE:-7}" \
    ${GPU_PATH:+$([ "$GPU_PATH" != "cpu" ] && echo "--ocl" || true)} \
    "$@"
