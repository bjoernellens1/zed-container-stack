#!/usr/bin/env python3
"""Export RGB-D frames and optional trajectory from a live ZED camera or SVO/SVO2 file."""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2
import numpy as np


def _load_zed():
    try:
        import pyzed.sl as sl  # type: ignore
        return sl
    except Exception as exc:
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


def timestamp_seconds(sl: Any, zed: Any) -> float:
    try:
        return float(zed.get_timestamp(sl.TIME_REFERENCE.IMAGE).get_nanoseconds()) * 1e-9
    except Exception:
        return time.time()


def pose_to_fields(pose: Any) -> tuple[list[float], list[float]]:
    t = pose.get_translation().get()
    q = pose.get_orientation().get()
    return [float(t[0]), float(t[1]), float(t[2])], [float(q[0]), float(q[1]), float(q[2]), float(q[3])]


def camera_info_dict(zed: Any) -> dict[str, Any]:
    try:
        info = zed.get_camera_information()
        cfg = info.camera_configuration
        cal = cfg.calibration_parameters
        left = cal.left_cam
        right = cal.right_cam
        return {
            "camera_model": str(getattr(info, "camera_model", "unknown")),
            "serial_number": getattr(info, "serial_number", None),
            "camera_firmware_version": getattr(info, "camera_firmware_version", None),
            "resolution": {"width": cfg.resolution.width, "height": cfg.resolution.height},
            "fps": cfg.fps,
            "left": {"fx": left.fx, "fy": left.fy, "cx": left.cx, "cy": left.cy, "disto": list(left.disto)},
            "right": {"fx": right.fx, "fy": right.fy, "cx": right.cx, "cy": right.cy, "disto": list(right.disto)},
            "baseline_m": abs(float(getattr(cal, "T", [0.0])[0])) / 1000.0 if hasattr(cal, "T") else None,
        }
    except Exception as exc:
        return {"error": f"failed to read camera info: {exc}"}


def main() -> int:
    ap = argparse.ArgumentParser(description="Export RGB-D and optional TUM trajectory from ZED live camera or SVO/SVO2.")
    src = ap.add_mutually_exclusive_group()
    src.add_argument("--svo", default=None, help="Input .svo/.svo2 file. If omitted, use live camera.")
    ap.add_argument("--out", required=True, help="Output dataset directory, e.g. /data/rgbd/run1")
    ap.add_argument("--resolution", default="HD720")
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--depth-mode", default="NEURAL_LIGHT")
    ap.add_argument("--units", default="METER")
    ap.add_argument("--coordinate-system", default="RIGHT_HANDED_Y_UP")
    ap.add_argument("--with-trajectory", action="store_true", help="Enable positional tracking and write trajectory_tum.txt + poses.csv")
    ap.add_argument("--tracking-mode", default="GEN_3")
    ap.add_argument("--depth-png", action="store_true", help="Write depth_png/*.png as uint16 millimeters")
    ap.add_argument("--depth-npy", action="store_true", help="Write depth_npy/*.npy as float32 meters")
    ap.add_argument("--right", action="store_true", help="Also export right camera images")
    ap.add_argument("--max-frames", type=int, default=0, help="Stop after N frames. 0 means all/unlimited.")
    ap.add_argument("--stride", type=int, default=1, help="Export every Nth grabbed frame.")
    args = ap.parse_args()

    if not args.depth_png and not args.depth_npy:
        args.depth_png = True

    sl = _load_zed()
    out = Path(args.out)
    rgb_dir = out / "rgb"
    right_dir = out / "right" if args.right else None
    depth_png_dir = out / "depth_png" if args.depth_png else None
    depth_npy_dir = out / "depth_npy" if args.depth_npy else None
    for d in [rgb_dir, right_dir, depth_png_dir, depth_npy_dir]:
        if d:
            d.mkdir(parents=True, exist_ok=True)

    init = sl.InitParameters()
    init.camera_resolution = enum_lookup(sl.RESOLUTION, args.resolution)
    init.camera_fps = args.fps
    init.coordinate_units = enum_lookup(sl.UNIT, args.units)
    init.coordinate_system = enum_lookup(sl.COORDINATE_SYSTEM, args.coordinate_system)
    init.depth_mode = enum_lookup(sl.DEPTH_MODE, args.depth_mode, getattr(sl.DEPTH_MODE, "NEURAL_LIGHT", None))
    if args.svo:
        init.set_from_svo_file(args.svo)
        try:
            init.svo_real_time_mode = False
        except Exception:
            pass

    zed = sl.Camera()
    err = zed.open(init)
    if err != sl.ERROR_CODE.SUCCESS:
        print(f"ERROR: zed.open() failed: {err}", file=sys.stderr)
        return 4

    tracking_enabled = False
    if args.with_trajectory:
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

    (out / "camera_info.json").write_text(json.dumps(camera_info_dict(zed), indent=2), encoding="utf-8")
    (out / "metadata.json").write_text(json.dumps({
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "source_svo": args.svo,
        "depth_mode": args.depth_mode,
        "trajectory": tracking_enabled,
        "sdk_version": getattr(sl.Camera, "get_sdk_version", lambda: "unknown")(),
    }, indent=2), encoding="utf-8")

    runtime = sl.RuntimeParameters()
    left = sl.Mat()
    right = sl.Mat() if args.right else None
    depth = sl.Mat()
    pose = sl.Pose()

    rgb_txt = open(out / "rgb.txt", "w", buffering=1)
    depth_txt = open(out / "depth.txt", "w", buffering=1) if args.depth_png else None
    tum_f = open(out / "trajectory_tum.txt", "w", buffering=1) if tracking_enabled else None
    csv_f = open(out / "poses.csv", "w", buffering=1) if tracking_enabled else None
    if csv_f:
        csv_f.write("timestamp,tx,ty,tz,qx,qy,qz,qw,tracking_state\n")

    grabbed = 0
    exported = 0
    try:
        while True:
            status = zed.grab(runtime)
            if args.svo and status == sl.ERROR_CODE.END_OF_SVOFILE_REACHED:
                break
            if status != sl.ERROR_CODE.SUCCESS:
                time.sleep(0.002)
                continue
            grabbed += 1
            if args.stride > 1 and (grabbed - 1) % args.stride != 0:
                continue
            if args.max_frames and exported >= args.max_frames:
                break

            ts = timestamp_seconds(sl, zed)
            stem = f"{exported:06d}"

            zed.retrieve_image(left, sl.VIEW.LEFT)
            img = left.get_data()
            bgr = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            rgb_path = rgb_dir / f"{stem}.png"
            cv2.imwrite(str(rgb_path), bgr)
            rgb_txt.write(f"{ts:.9f} rgb/{stem}.png\n")

            if args.right and right is not None and right_dir is not None:
                zed.retrieve_image(right, sl.VIEW.RIGHT)
                rbgr = cv2.cvtColor(right.get_data(), cv2.COLOR_BGRA2BGR)
                cv2.imwrite(str(right_dir / f"{stem}.png"), rbgr)

            zed.retrieve_measure(depth, sl.MEASURE.DEPTH)
            depth_m = depth.get_data().astype(np.float32, copy=True)
            depth_m[~np.isfinite(depth_m)] = 0.0
            depth_m[depth_m < 0] = 0.0

            if depth_npy_dir is not None:
                np.save(depth_npy_dir / f"{stem}.npy", depth_m)
            if depth_png_dir is not None and depth_txt is not None:
                depth_mm = np.clip(depth_m * 1000.0, 0, np.iinfo(np.uint16).max).astype(np.uint16)
                cv2.imwrite(str(depth_png_dir / f"{stem}.png"), depth_mm)
                depth_txt.write(f"{ts:.9f} depth_png/{stem}.png\n")

            if tracking_enabled and tum_f and csv_f:
                state = zed.get_position(pose, sl.REFERENCE_FRAME.WORLD)
                t, q = pose_to_fields(pose)
                tum_f.write(f"{ts:.9f} {t[0]:.9f} {t[1]:.9f} {t[2]:.9f} {q[0]:.9f} {q[1]:.9f} {q[2]:.9f} {q[3]:.9f}\n")
                csv_f.write(f"{ts:.9f},{t[0]:.9f},{t[1]:.9f},{t[2]:.9f},{q[0]:.9f},{q[1]:.9f},{q[2]:.9f},{q[3]:.9f},{state}\n")

            exported += 1
            if exported % 100 == 0:
                print(f"exported={exported}")
    finally:
        rgb_txt.close()
        if depth_txt:
            depth_txt.close()
        if tum_f:
            tum_f.close()
        if csv_f:
            csv_f.close()
        if tracking_enabled:
            try:
                zed.disable_positional_tracking()
            except Exception:
                pass
        zed.close()

    print(f"Done. Exported {exported} frames to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
