#!/usr/bin/env bash
set -euo pipefail
OUT=${1:-/data/rosbags/zed_$(date +%Y%m%d_%H%M%S)}
MODEL=${ZED_CAMERA_MODEL:-zed2i}
source /opt/ros/${ROS_DISTRO:-jazzy}/setup.bash
source /opt/zed_ros2_ws/install/setup.bash

echo "Starting ZED wrapper for camera_model=${MODEL}"
ros2 launch zed_wrapper zed_camera.launch.py camera_model:=${MODEL} &
LAUNCH_PID=$!
trap 'kill ${LAUNCH_PID} >/dev/null 2>&1 || true' EXIT
sleep 8

echo "Available ZED topics:"
ros2 topic list | grep -E 'zed|tf' || true

echo "Recording bag to ${OUT}"
ros2 bag record -s mcap -o "${OUT}" \
  /tf /tf_static \
  /zed/zed_node/rgb/camera_info \
  /zed/zed_node/rgb/color/rect/image \
  /zed/zed_node/depth/depth_registered \
  /zed/zed_node/odom \
  /zed/zed_node/pose \
  /zed/zed_node/path_odom \
  /zed/zed_node/path_map \
  /zed/zed_node/imu/data
