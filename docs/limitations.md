# Limitations

## CUDA requirement

The official ZED SDK depth and positional tracking pipeline requires NVIDIA CUDA on Linux. This is why the AMD, Intel, and CPU profiles are fallback profiles.

## Non-NVIDIA fallback quality

`zed-open-capture` can access raw frames, sensors, calibration, and example OpenCV depth, but it does not reproduce the Stereolabs SDK depth models or VIO/SLAM.

## Docker tag drift

Stereolabs Docker tags change with SDK releases and CUDA/TensorRT versions. Use `scripts/list-zed-tags.sh` before assuming the default `.env.example` tag is still available.

## ZED X / GMSL2

ZED X cameras may require host-side ZED Link/GMSL driver setup. This repository primarily targets USB ZED cameras from Fedora hosts.
