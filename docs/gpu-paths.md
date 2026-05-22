# GPU and backend paths

## CPU / Intel iGPU / AMD (default — no NVIDIA required)

Uses `zed-open-capture` (official Stereolabs library) + OpenCV `StereoSGBM` to produce
properly calibrated, rectified depth aligned to the left RGB image.

**How depth works without NVIDIA:**
1. Factory calibration is read from the ZED camera via its serial number and downloaded
   from Stereolabs servers on first use (cached locally after that).
2. Left + right frames are rectified using the official calibration maps.
3. OpenCV `StereoSGBM` computes disparity from the rectified stereo pair on CPU.
4. Depth is derived as `depth_mm = fx_px × baseline_m × 1000 / disparity_px`.

Depth quality is lower than the NVIDIA NEURAL/NEURAL_LIGHT modes but uses the same
factory calibration, so the geometry is correct.

### Quickstart

```bash
make init
# Build the opencapture image (downloads zed-open-capture, compiles recorder)
docker compose --profile cpu build zed-cpu-opencapture

# Record depth + RGB on CPU
make cpu-capture SESSION=myrun

# Record with Intel iGPU OpenCL acceleration (/dev/dri must be present)
make intel-capture SESSION=myrun
```

### Output directory layout

```
data/rgbd/myrun/
├── rgb/           000000.png … (left camera BGR, rectified)
├── depth_png/     000000.png … (uint16, millimeters, aligned to left)
├── rgb.txt        (TUM: timestamp rgb/NNNNNN.png)
├── depth.txt      (TUM: timestamp depth_png/NNNNNN.png)
├── calibration.json  (fx, fy, cx, cy, baseline_m, serial_number …)
└── metadata.json
```

This format is identical to `zed_export_rgbd_trajectory.py` (NVIDIA path), so
downstream processing tools work with both outputs.

### Manual / interactive use

```bash
# Drop into a shell
make cpu-shell
make intel-shell

# Run the recorder directly with custom settings
zed_oc_depth_recorder --out /data/rgbd/test --fps 15 --num-disp 64

# Use the Python wrapper (reads ZED_* env vars)
python3 /workspace/tools/zed_oc_record.py --session test --ocl

# Reference binaries from zed-open-capture samples
zed_open_capture_video_example   # raw stereo viewer
zed_open_capture_depth_example   # SGBM depth viewer (display only, no saving)
```

### SGBM tuning

Set these in `.env` to tune depth quality vs speed:

| Variable | Default | Notes |
|---|---|---|
| `ZED_OC_SGBM_NUM_DISP` | `128` | Multiple of 16. Higher = more depth range, slower. |
| `ZED_OC_SGBM_BLOCK_SIZE` | `7` | Odd integer ≥ 5. Larger = smoother depth, less edge detail. |

### Intel iGPU — OpenCL acceleration

The intel profile passes `/dev/dri` into the container. If Fedora's OpenCV was compiled
with OpenCL support (default), the SGBM remap and compute steps can use the iGPU via
`cv::ocl`. Pass `--ocl` to the recorder (or use `make intel-capture` which sets
`GPU_PATH=intel` and enables it automatically).

### AMD GPU

Same as Intel but also passes `/dev/kfd` for ROCm/HSA access. OpenCL SGBM acceleration
applies if Mesa's OpenCL ICD is present.

```bash
docker compose --profile amd build zed-amd-opencapture
docker compose --profile amd run --rm zed-amd-opencapture \
  bash -lc '/workspace/scripts/cpu-depth-record.sh myrun'
```

### First-run calibration note

The recorder calls `sl_oc::tools::initCalibration()` which downloads a `.conf` file
from `https://calib.stereolabs.com/?SN=<serial>` on the first run for a given camera.
The file is cached locally so subsequent runs work offline. If the download fails, check
that the container can reach the internet (`network_mode: host` is set in compose.yaml).

---

## NVIDIA (full ZED SDK)

Use this when you want the full SDK pipeline: NEURAL depth, positional tracking,
SVO/SVO2, ZED Explorer, ZED Depth Viewer, and ROS 2 wrapper.

Requires NVIDIA GPU + NVIDIA Container Toolkit on the host.

```bash
make init
./scripts/list-zed-tags.sh | grep -E '5\.3|ubuntu24|cuda12|cuda13|py|tools'
make viewer
make record-svo-pose SESSION=myrun
make export-rgbd SVO=data/svo/myrun.svo2
```
