#!/usr/bin/env bash
set -euo pipefail
if [[ $# -lt 1 ]]; then
  echo "Usage: $0 data/svo/file.svo2 [out-name]" >&2
  exit 2
fi
SVO=$1
NAME=${2:-$(basename "$SVO" .svo2)}
${COMPOSE:-docker compose} --profile nvidia-sdk run --rm zed-nvidia-sdk bash -lc "python3 /workspace/tools/zed_export_rgbd_trajectory.py --svo /${SVO} --out /data/rgbd/${NAME} --with-trajectory --depth-png --depth-npy"
