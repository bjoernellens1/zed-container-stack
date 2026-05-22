#!/usr/bin/env bash
set -euo pipefail
printf '\n== Host ==\n'
uname -a
printf '\n== GPU ==\n'
command -v nvidia-smi >/dev/null && nvidia-smi || true
command -v rocm-smi >/dev/null && rocm-smi || true
lspci | grep -Ei 'vga|3d|display' || true
printf '\n== USB ZED candidates ==\n'
lsusb | grep -Ei 'stereo|zed|2b03|stereolabs|8086' || true
printf '\n== Containers ==\n'
command -v docker >/dev/null && docker version --format '{{.Server.Version}}' || true
command -v podman >/dev/null && podman version || true
printf '\n== Display ==\n'
echo "DISPLAY=${DISPLAY:-}"; echo "WAYLAND_DISPLAY=${WAYLAND_DISPLAY:-}"; echo "XDG_RUNTIME_DIR=${XDG_RUNTIME_DIR:-}"
