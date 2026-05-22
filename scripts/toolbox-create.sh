#!/usr/bin/env bash
set -euo pipefail
IMAGE=localhost/zed-fedora-stack:toolbox
CONTAINER=zed-fedora-stack
if ! podman image exists "$IMAGE"; then
  podman build -t "$IMAGE" -f toolbx/Containerfile .
fi
toolbox create --image "$IMAGE" --container "$CONTAINER" || true
echo "Enter with: toolbox enter $CONTAINER"
