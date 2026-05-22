#!/usr/bin/env python3
"""Convenience wrapper around zed_oc_depth_recorder for CPU/Intel/AMD capture.

Handles output directory creation, default paths, and subprocess invocation.
Requires the opencapture container (or zed_oc_depth_recorder on PATH).

Usage inside the container:
    python3 /workspace/tools/zed_oc_record.py --session myrun
    python3 /workspace/tools/zed_oc_record.py --session myrun --frames 300 --ocl
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Record ZED 2 depth+RGB via CPU/iGPU (wraps zed_oc_depth_recorder)."
    )
    ap.add_argument("--session", default=None,
                    help="Session name used as subdirectory under /data/rgbd/. "
                         "Defaults to timestamp.")
    ap.add_argument("--out", default=None,
                    help="Full output path (overrides --session).")
    ap.add_argument("--frames", type=int, default=0,
                    help="Max frames to record (0 = unlimited).")
    ap.add_argument("--fps", type=int, default=int(os.environ.get("ZED_FPS", "30")))
    ap.add_argument("--resolution", default=os.environ.get("ZED_RESOLUTION", "HD720"),
                    choices=["HD720", "HD1080", "HD2K", "VGA"])
    ap.add_argument("--num-disp", type=int,
                    default=int(os.environ.get("ZED_OC_SGBM_NUM_DISP", "128")))
    ap.add_argument("--block-size", type=int,
                    default=int(os.environ.get("ZED_OC_SGBM_BLOCK_SIZE", "7")))
    ap.add_argument("--ocl", action="store_true",
                    help="Enable OpenCL (Intel iGPU / AMD via Mesa). "
                         "Auto-enabled when GPU_PATH != 'cpu'.")
    args = ap.parse_args()

    # Output directory
    if args.out:
        out = Path(args.out)
    else:
        session = args.session or datetime.now().strftime("%Y%m%d_%H%M%S")
        out = Path("/data/rgbd") / session

    out.mkdir(parents=True, exist_ok=True)
    print(f"Output: {out}")

    # Auto-enable OpenCL for intel/amd profiles
    gpu_path = os.environ.get("GPU_PATH", "cpu")
    use_ocl = args.ocl or (gpu_path not in ("cpu", ""))

    cmd = [
        "zed_oc_depth_recorder",
        "--out", str(out),
        "--fps", str(args.fps),
        "--resolution", args.resolution,
        "--num-disp", str(args.num_disp),
        "--block-size", str(args.block_size),
    ]
    if args.frames > 0:
        cmd += ["--frames", str(args.frames)]
    if use_ocl:
        cmd.append("--ocl")

    print("Running:", " ".join(cmd))
    try:
        result = subprocess.run(cmd)
        return result.returncode
    except KeyboardInterrupt:
        return 0
    except FileNotFoundError:
        print(
            "ERROR: zed_oc_depth_recorder not found. "
            "Build the opencapture container first:\n"
            "  docker compose --profile cpu build zed-cpu-opencapture",
            file=sys.stderr,
        )
        return 127


if __name__ == "__main__":
    raise SystemExit(main())
