#!/usr/bin/env python3
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


def run(cmd: list[str]) -> int:
    print(f"\n$ {' '.join(cmd)}")
    try:
        p = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=20)
        print(p.stdout.strip())
        return p.returncode
    except Exception as exc:
        print(f"failed: {exc}")
        return 1


def main() -> int:
    print("== ZED Fedora Stack system check ==")
    print(f"DISPLAY={os.environ.get('DISPLAY')}")
    print(f"WAYLAND_DISPLAY={os.environ.get('WAYLAND_DISPLAY')}")
    print(f"XDG_RUNTIME_DIR={os.environ.get('XDG_RUNTIME_DIR')}")
    print(f"/dev/bus/usb exists={Path('/dev/bus/usb').exists()}")
    print(f"/dev/dri exists={Path('/dev/dri').exists()}")

    for cmd in (["nvidia-smi"], ["lsusb"], ["v4l2-ctl", "--list-devices"], ["glxinfo", "-B"]):
        if shutil.which(cmd[0]):
            run(cmd)

    print("\n== Python API ==")
    try:
        import pyzed.sl as sl  # type: ignore
        print(f"pyzed import OK, SDK version: {sl.Camera.get_sdk_version()}")
    except Exception as exc:
        print(f"pyzed import failed: {exc}")

    for tool in ["/usr/local/zed/tools/ZED_Diagnostic", "/usr/local/zed/tools/ZED_Explorer", "/usr/local/zed/tools/ZED_Depth_Viewer"]:
        print(f"{tool}: {'present' if Path(tool).exists() else 'missing'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
