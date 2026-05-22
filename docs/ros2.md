# ROS 2 path

The ROS 2 image builds on the ZED SDK base image and installs ROS 2 Jazzy plus `stereolabs/zed-ros2-wrapper`.

Build:

```bash
docker compose --profile nvidia-ros2 build zed-nvidia-ros2
```

Record:

```bash
make ros2-record SESSION=office_zed
```

The default recorder captures:

```text
/tf
/tf_static
/zed/zed_node/rgb/camera_info
/zed/zed_node/rgb/color/rect/image
/zed/zed_node/depth/depth_registered
/zed/zed_node/odom
/zed/zed_node/pose
/zed/zed_node/path_odom
/zed/zed_node/path_map
/zed/zed_node/imu/data
```

Topic names can change with wrapper parameters. Always check:

```bash
ros2 topic list | grep zed
```
