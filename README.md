# zed-fedora-stack

Container-first ZED camera stack for Fedora hosts.

This repository is designed for a Fedora workstation/laptop where the native ZED SDK installer is not the best route. It provides one compose file with separate execution paths for NVIDIA, AMD, Intel iGPU, and CPU-only systems.

## What works where

| Path | Backend | ZED SDK depth | ZED SDK positional tracking | GUI tools | Intended use |
|---|---|---:|---:|---:|---|
| `nvidia-sdk` | Official Stereolabs SDK image + CUDA | yes | yes | yes, `ZED_Explorer`, `ZED_Depth_Viewer` | Real RGB-D/SVO/SVO2 recording and trajectory export |
| `nvidia-ros2` | ZED SDK + ROS 2 wrapper | yes | yes | yes, RViz2/ZED tools | ROS 2 bag recording for SLAM pipelines |
| `amd` | `zed-open-capture` + OpenCV | no official SDK depth | no official SDK tracking | OpenCV examples | Raw stereo/sensor capture and experimental OpenCV stereo depth |
| `intel` | `zed-open-capture` + OpenCV | no official SDK depth | no official SDK tracking | OpenCV examples | Same fallback path on Intel iGPU machines |
| `cpu` | `zed-open-capture` + OpenCV | no official SDK depth | no official SDK tracking | OpenCV examples | Debugging, calibration, raw capture |
| `toolbx` | Fedora toolbox helper | no official SDK depth | no official SDK tracking | host-integrated CLI/GUI helpers | Fedora-native dev shell for fallback/debug tooling |

The limitation is architectural: on Linux, the official ZED SDK depth/tracking stack requires NVIDIA CUDA. Non-NVIDIA paths are useful, but they are not equivalent to the ZED SDK pipeline.

## Quick start

```bash
sudo dnf install -y git make docker docker-compose-plugin xorg-x11-server-utils
sudo systemctl enable --now docker

git clone <your-repo-url> zed-fedora-stack
cd zed-fedora-stack
make init
./scripts/host-diagnose.sh
```

Edit `.env` and choose a valid `stereolabs/zed` image tag. You can list tags with:

```bash
./scripts/list-zed-tags.sh | grep -E '5\.3|ubuntu24|cuda12|cuda13|py|tools'
```

Allow local GUI windows from the container:

```bash
make gui-allow
```

Run the official ZED Explorer GUI:

```bash
make viewer
```

Run the diagnostic:

```bash
make diagnostic
```

Record SVO/SVO2 only:

```bash
make record-svo SESSION=test01
```

Record SVO/SVO2 and a sidecar trajectory:

```bash
make record-svo-pose SESSION=test01_pose
```

Export RGB-D and poses from an SVO2 file:

```bash
make export-rgbd SVO=data/svo/test01_pose.svo2
```

The exported dataset lands in:

```text
data/rgbd/test01_pose/
├── rgb/000000.png
├── depth_png/000000.png      # uint16 millimeters
├── depth_npy/000000.npy      # float32 meters
├── rgb.txt                   # TUM-style associations
├── depth.txt
├── trajectory_tum.txt        # timestamp tx ty tz qx qy qz qw
├── poses.csv
├── camera_info.json
└── metadata.json
```

## Fedora host prerequisites

### NVIDIA path

You need a working NVIDIA driver on the Fedora host:

```bash
nvidia-smi
```

Install NVIDIA Container Toolkit from the RPM repo:

```bash
curl -s -L https://nvidia.github.io/libnvidia-container/stable/rpm/nvidia-container-toolkit.repo \
  | sudo tee /etc/yum.repos.d/nvidia-container-toolkit.repo
sudo dnf install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

Test GPU passthrough:

```bash
docker run --rm --gpus all nvidia/cuda:12.9.1-base-ubuntu24.04 nvidia-smi
```

### USB permissions

For robust non-root camera access on the host, install the udev rule:

```bash
./scripts/udev-install-fedora.sh
```

The compose services are intentionally `privileged` because USB camera access and GUI/GPU devices are otherwise fiddly across Docker, Podman, and rootless modes. You can harden this later once the pipeline is stable.

## Docker usage

Shell into the SDK container:

```bash
docker compose --profile nvidia-sdk run --rm zed-nvidia-sdk bash
```

Run tools manually:

```bash
/usr/local/zed/tools/ZED_Explorer
/usr/local/zed/tools/ZED_Depth_Viewer
/usr/local/zed/tools/ZED_Diagnostic -c
python3 /workspace/tools/zed_system_check.py
```

Record directly:

```bash
python3 /workspace/tools/zed_record_svo.py \
  --out /data/svo/manual.svo2 \
  --duration 60 \
  --resolution HD720 \
  --fps 30
```

Record with tracking sidecars:

```bash
python3 /workspace/tools/zed_record_svo.py \
  --out /data/svo/manual_pose.svo2 \
  --enable-tracking \
  --trajectory /data/svo/manual_pose_tum.txt \
  --trajectory-csv /data/svo/manual_pose.csv
```

Export from SVO/SVO2:

```bash
python3 /workspace/tools/zed_export_rgbd_trajectory.py \
  --svo /data/svo/manual_pose.svo2 \
  --out /data/rgbd/manual_pose \
  --with-trajectory \
  --depth-png \
  --depth-npy
```

## Podman usage

Podman Compose can work for the fallback paths and often works for GUI/device access, but NVIDIA GPU passthrough is less standardized than Docker Compose. Try:

```bash
COMPOSE='podman compose' make viewer
```

If that fails for NVIDIA, use the explicit Podman launcher:

```bash
./scripts/podman-nvidia-run.sh /usr/local/zed/tools/ZED_Explorer
./scripts/podman-nvidia-run.sh python3 /workspace/tools/zed_system_check.py
```

For AMD/Intel/CPU fallback images:

```bash
podman compose --profile amd run --rm zed-amd-opencapture bash
podman compose --profile intel run --rm zed-intel-opencapture bash
podman compose --profile cpu run --rm zed-cpu-opencapture bash
```

## Toolbox usage

Build and create the toolbox-compatible helper image:

```bash
make toolbox-build
make toolbox-create
toolbox enter zed-fedora-stack
```

The toolbox path is for Fedora-native helper development and `zed-open-capture`-style fallback workflows. Do not expect the official Ubuntu ZED SDK to run natively inside a normal Fedora toolbox.

## ROS 2 recording path

Build the ROS 2 image:

```bash
docker compose --profile nvidia-ros2 build zed-nvidia-ros2
```

Record the default set of useful ZED topics:

```bash
make ros2-record SESSION=zed_ros2_test
```

This starts the ZED ROS 2 wrapper and records RGB, camera info, registered depth, odometry, pose, path, IMU, `/tf`, and `/tf_static` to MCAP.

Inspect topics manually:

```bash
docker compose --profile nvidia-ros2 run --rm zed-nvidia-ros2 bash
ros2 launch zed_wrapper zed_camera.launch.py camera_model:=zed2i
ros2 topic list | grep zed
```

## GUI notes on Fedora KDE/GNOME Wayland

The Stereolabs GUI tools are easiest through X11/Xwayland. The stack mounts `/tmp/.X11-unix` and forwards `DISPLAY`. Run:

```bash
make gui-allow
make viewer
```

When finished:

```bash
make gui-deny
```

If OpenGL errors occur, test:

```bash
./scripts/podman-nvidia-run.sh glxinfo -B
# or inside Docker compose shell:
glxinfo -B
```

## Why SVO first?

For repeatable SLAM experiments, prefer recording SVO2 first, then exporting RGB-D/pose or replaying through ROS 2. SVO2 is the closest thing to a raw master recording in the ZED ecosystem and lets you regenerate depth/tracking with different SDK settings later.

## Known limitations

1. Official ZED SDK depth and tracking are NVIDIA CUDA paths. AMD, Intel, and CPU-only profiles are fallback profiles using `zed-open-capture` and OpenCV examples.
2. The default Stereolabs Docker tag in `.env.example` may need adjustment because Docker tags change with SDK/CUDA releases. Use `./scripts/list-zed-tags.sh`.
3. Rootless Podman plus USB plus NVIDIA GUI is possible but brittle. Use Docker or rootful Podman first.
4. ZED X / GMSL2 cameras may require additional host driver setup not covered here. This repo is primarily for USB ZED/ZED Mini/ZED 2/ZED 2i style workflows.
5. The OpenCV fallback depth from `zed-open-capture` is not geometrically equivalent to ZED SDK depth.

## Repository layout

```text
compose.yaml                    # unified compose file with profiles
Containerfile.nvidia-tools       # optional SDK helper image
Containerfile.ros2               # SDK + ROS 2 wrapper image
Containerfile.opencapture        # Fedora zed-open-capture fallback image
toolbx/Containerfile             # toolbox-compatible Fedora helper image
tools/zed_record_svo.py          # SVO/SVO2 recorder, optional trajectory sidecar
tools/zed_export_rgbd_trajectory.py # RGB-D + TUM pose exporter
tools/zed_system_check.py        # diagnostics from inside container
scripts/                         # launchers for GUI, recording, Podman, toolbox, ROS 2
data/                            # ignored output folders
```
