#!/usr/bin/env bash
set -euo pipefail
cat <<'RULES' | sudo tee /etc/udev/rules.d/99-stereolabs-zed.rules >/dev/null
# Stereolabs ZED USB cameras. Vendor id 2b03 is used by Stereolabs USB cameras.
SUBSYSTEM=="usb", ATTR{idVendor}=="2b03", MODE="0666", TAG+="uaccess"
KERNEL=="hidraw*", ATTRS{idVendor}=="2b03", MODE="0666", TAG+="uaccess"
RULES
sudo udevadm control --reload-rules
sudo udevadm trigger
