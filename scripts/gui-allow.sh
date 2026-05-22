#!/usr/bin/env bash
set -euo pipefail
if command -v xhost >/dev/null 2>&1; then
  xhost +SI:localuser:root >/dev/null || true
  xhost +SI:localuser:"${USER}" >/dev/null || true
  echo "X11 access allowed for local root and ${USER}."
else
  echo "xhost not found. Install xorg-x11-xhost on Fedora if GUI forwarding fails."
fi
