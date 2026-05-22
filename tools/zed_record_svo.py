#!/usr/bin/env python3
"""Record ZED SVO/SVO2 files, optionally with live trajectory sidecars.

This script intentionally stays close to the official pyzed API and avoids ROS.
It is meant to run inside an official Stereolabs ZED SDK container.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _load_zed():
    try:
        import pyzed.sl as sl  # type: ignore
        return sl
    except Exception as exc:  # pragma: no cover - runtime environment dependent
        print("ERROR: Could not import pyzed.sl. Use a Stereolabs ZED SDK Python image or install pyzed.", file=sys.stderr)
        print(f"Import error: {exc}", file=sys.stderr)
        sys.exit(3)


def enum_lookup(enum_cls: Any, name: str, default: Any | None = None) -> Any:
    normalized = str(name).strip().upper().replace("-", "_").replace(" ", "_")
    if hasattr(enum_cls, normalized):
        return getattr(enum_cls, normalized)
    if default is not None:
        return default
    available = [k for k in dir(enum_cls) if k.isupper()]
    raise ValueError(f"Unknown {enum_cls}: {name}. Available: {', '.join(available)}")


def pose_to_fields(sl: Any, pose: Any) -> tuple[list[float], list[float]]:
    t = pose.get_translation().get()
    q = pose.get_orientation().get()
    return [float(t[0]), float(t[1]), float(t[2])], [float(q[0]), float(q[1]), float(q[2]), float(q[3])]


def timestamp_seconds(sl: Any, zed: Any) -> float:
    try:
        return float(zed.get_timestamp(sl.TIME_REFERENCE.IMAGE).get_nanoseconds()) * 1e-9
    except Exception:
        return time.time()


def set_monotonic_clock_if_available(sl: Any) -> None:
    try:
        if hasattr(sl, "set_timestamp_clock") and hasattr(sl, "TIMESTAMP_CLOCK"):
            sl.set_timestamp_clock(sl.TIMESTAMP_CLOCK.MONOTONIC_CLOCK)
            print("Using ZED monotonic timestamp clock.")
    except Exception as exc:
        print(f"WARNING: Could not enable monotonic timestamp clock: {exc}", file=sys.stderr)


def main() -> int:
    ap = argparse.ArgumentParser(description="Record a ZED SVO/SVO2 file with optional TUM/CSV trajectory sidecars.")
    ap.add_argument("--out", required=True, help="Output .svo or .svo2 path inside the container, e.g. /data/svo/run.svo2")
    ap.add_argument("--duration", type=float, default=0.0, help="Recording duration in seconds. 0 means until Ctrl+C.")
    ap.add_argument("--resolution", default="HD720", help="ZED resolution enum, e.g. HD720, HD1080, HD2K, VGA")
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--depth-mode", default="NEURAL_LIGHT", help="Depth mode for tracking/depth init. Use NONE to disable depth.")
    ap.add_argument("--units", default="METER", help="Coordinate/depth unit enum, default METER")
    ap.add_argument("--coordinate-system", default="RIGHT_HANDED_Y_UP")
    ap.add_argument("--compression", default="H264", help="SVO_COMPRESSION_MODE, e.g. H264, H265, LOSSLESS")
    ap.add_argument("--encoding-preset", default="FAST", help="SVO_ENCODING_PRESET if SDK supports it: DEFAULT, ULTRAFAST, FAST, MEDIUM, SLOW")
    ap.add_argument("--enable-tracking", action="store_true", help="Enable positional tracking and write pose logs if requested.")
    ap.add_argument("--tracking-mode", default="GEN_3", help="POSITIONAL_TRACKING_MODE if supported, default GEN_3")
    ap.add_argument("--trajectory", default=None, help="Write TUM trajectory: timestamp tx ty tz qx qy qz qw")
    ap.add_argument("--trajectory-csv", default=None, help="Write richer CSV trajectory with tracking state")
    ap.add_argument("--monotonic-clock", action="store_true", help="Use SDK monotonic timestamp clock when available.")
    args = ap.parse_args()

    sl = _load_zed()
    if args.monotonic_clock:
        set_monotonic_clock_if_available(sl)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    init = sl.InitParameters()
    init.camera_resolution = enum_lookup(sl.RESOLUTION, args.resolution)
    init.camera_fps = args.fps
    init.coordinate_units = enum_lookup(sl.UNIT, args.units)
    init.coordinate_system = enum_lookup(sl.COORDINATE_SYSTEM, args.coordinate_system)
    init.depth_mode = enum_lookup(sl.DEPTH_MODE, args.depth_mode, getattr(sl.DEPTH_MODE, "NEURAL_LIGHT", None))

    zed = sl.Camera()
    err = zed.open(init)
    if err != sl.ERROR_CODE.SUCCESS:
        print(f"ERROR: zed.open() failed: {err}", file=sys.stderr)
        return 4

    tracking_enabled = False
    if args.enable_tracking or args.trajectory or args.trajectory_csv:
        tracking_params = sl.PositionalTrackingParameters()
        try:
            tracking_params.mode = enum_lookup(sl.POSITIONAL_TRACKING_MODE, args.tracking_mode)
        except Exception as exc:
            print(f"WARNING: Could not set tracking mode {args.tracking_mode}: {exc}", file=sys.stderr)
        try:
            tracking_params.enable_imu_fusion = True
        except Exception:
            pass
        err = zed.enable_positional_tracking(tracking_params)
        if err != sl.ERROR_CODE.SUCCESS:
            print(f"ERROR: enable_positional_tracking() failed: {err}", file=sys.stderr)
            zed.close()
            return 5
        tracking_enabled = True

    rec = sl.RecordingParameters()
    rec.video_filename = str(out)
    rec.compression_mode = enum_lookup(sl.SVO_COMPRESSION_MODE, args.compression)
    if hasattr(sl, "SVO_ENCODING_PRESET") and hasattr(rec, "encoding_preset"):
        try:
            rec.encoding_preset = enum_lookup(sl.SVO_ENCODING_PRESET, args.encoding_preset)
        except Exception as exc:
            print(f"WARNING: Could not set encoding preset: {exc}", file=sys.stderr)

    err = zed.enable_recording(rec)
    if err != sl.ERROR_CODE.SUCCESS:
        print(f"ERROR: enable_recording() failed: {err}", file=sys.stderr)
        zed.close()
        return 6

    tum_f = open(args.trajectory, "w", buffering=1) if args.trajectory else None
    csv_f = open(args.trajectory_csv, "w", newline="", buffering=1) if args.trajectory_csv else None
    csv_writer = None
    if csv_f:
        csv_writer = csv.writer(csv_f)
        csv_writer.writerow(["timestamp", "tx", "ty", "tz", "qx", "qy", "qz", "qw", "tracking_state"])

    meta = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "out": str(out),
        "resolution": args.resolution,
        "fps": args.fps,
        "depth_mode": args.depth_mode,
        "compression": args.compression,
        "tracking_enabled": tracking_enabled,
        "sdk_version": getattr(sl.Camera, "get_sdk_version", lambda: "unknown")(),
    }
    out.with_suffix(out.suffix + ".json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    runtime = sl.RuntimeParameters()
    pose = sl.Pose()
    stop = False

    def _stop(_signum, _frame):
        nonlocal stop
        stop = True

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    print(f"Recording to {out}. Press Ctrl+C to stop.")
    t0 = time.time()
    frames = 0
    try:
        while not stop:
            if args.duration > 0 and (time.time() - t0) >= args.duration:
                break
            err = zed.grab(runtime)
            if err != sl.ERROR_CODE.SUCCESS:
                time.sleep(0.002)
                continue
            frames += 1
            if tracking_enabled and (tum_f or csv_writer):
                state = zed.get_position(pose, sl.REFERENCE_FRAME.WORLD)
                ts = timestamp_seconds(sl, zed)
                t, q = pose_to_fields(sl, pose)
                if tum_f:
                    tum_f.write(f"{ts:.9f} {t[0]:.9f} {t[1]:.9f} {t[2]:.9f} {q[0]:.9f} {q[1]:.9f} {q[2]:.9f} {q[3]:.9f}\n")
                if csv_writer:
                    csv_writer.writerow([f"{ts:.9f}", *[f"{v:.9f}" for v in t], *[f"{v:.9f}" for v in q], str(state)])
            if frames % max(args.fps * 5, 1) == 0:
                print(f"frames={frames} elapsed={time.time() - t0:.1f}s")
    finally:
        zed.disable_recording()
        if tracking_enabled:
            try:
                zed.disable_positional_tracking()
            except Exception:
                pass
        zed.close()
        if tum_f:
            tum_f.close()
        if csv_f:
            csv_f.close()

    print(f"Done. Recorded {frames} frames to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
