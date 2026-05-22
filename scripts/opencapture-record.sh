#!/usr/bin/env bash
set -euo pipefail
OUT=${1:-/data/opencapture_$(date +%Y%m%d_%H%M%S)}
mkdir -p "$OUT"
cat > "$OUT/README.txt" <<'TXT'
This directory was created for CUDA-free ZED capture.
Use the zed-open-capture examples inside the container:
  zed_open_capture_video_example
  zed_open_capture_rectify_example
  zed_open_capture_depth_example
  zed_open_capture_sensors_example
For production recording on AMD/Intel/CPU, add a small C++ recorder around
sl_oc::video::VideoCapture::getLastFrame() and sl_oc::sensors::SensorCapture.
TXT
zed_open_capture_video_example
