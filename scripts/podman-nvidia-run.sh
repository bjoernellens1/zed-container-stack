#!/usr/bin/env bash
set -euo pipefail
IMAGE="${ZED_PY_IMAGE:-stereolabs/zed:5.3-py-devel-cuda12.8-ubuntu24.04}"
CMD=("${@:-bash}")
./scripts/gui-allow.sh || true
exec podman run --rm -it \
  --security-opt label=disable \
  --privileged \
  --network host \
  --ipc host \
  --device nvidia.com/gpu=all \
  --device /dev/bus/usb:/dev/bus/usb \
  --device /dev/dri:/dev/dri \
  -e DISPLAY="${DISPLAY:-:0}" \
  -e WAYLAND_DISPLAY="${WAYLAND_DISPLAY:-wayland-0}" \
  -e XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/tmp}" \
  -e QT_X11_NO_MITSHM=1 \
  -e NVIDIA_VISIBLE_DEVICES=all \
  -e NVIDIA_DRIVER_CAPABILITIES=all,compute,utility,graphics,display,video \
  -v "${PWD}/data:/data:Z" \
  -v "${PWD}/tools:/workspace/tools:Z" \
  -v "${PWD}/scripts:/workspace/scripts:Z" \
  -v /tmp/.X11-unix:/tmp/.X11-unix:ro \
  -v "${XDG_RUNTIME_DIR:-/tmp}:${XDG_RUNTIME_DIR:-/tmp}" \
  -v /run/udev:/run/udev:ro \
  -w /workspace \
  "$IMAGE" "${CMD[@]}"
