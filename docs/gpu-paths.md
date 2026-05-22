# GPU and backend paths

## NVIDIA

Use this when you want the real ZED SDK pipeline: depth, tracking, SVO/SVO2, ZED Explorer, ZED Depth Viewer, and ROS 2 wrapper.

Recommended commands:

```bash
make init
./scripts/list-zed-tags.sh | grep -E '5\.3|ubuntu24|cuda12|cuda13|py|tools'
make viewer
make record-svo-pose SESSION=myrun
make export-rgbd SVO=data/svo/myrun.svo2
```

## AMD GPU

The AMD profile intentionally does not attempt to run the ZED SDK. It builds a Fedora container with `zed-open-capture`, OpenCV, `/dev/dri`, and `/dev/kfd` access.

```bash
docker compose --profile amd build zed-amd-opencapture
docker compose --profile amd run --rm zed-amd-opencapture bash
zed_open_capture_video_example
zed_open_capture_depth_example
```

This gives raw stereo/sensor capture and OpenCV-style stereo depth experiments, not Stereolabs SDK depth or VIO.

## Intel iGPU

Same fallback idea as AMD, but only `/dev/dri` is passed:

```bash
docker compose --profile intel run --rm zed-intel-opencapture bash
zed_open_capture_video_example
```

## CPU only

Useful for debugging USB access and building fallback tools:

```bash
docker compose --profile cpu run --rm zed-cpu-opencapture bash
zed_open_capture_video_example
```
