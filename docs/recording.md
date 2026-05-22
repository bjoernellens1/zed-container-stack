# Recording workflows

## 1. SVO/SVO2 master recording

```bash
make record-svo SESSION=scene01
```

Output:

```text
data/svo/scene01.svo2
data/svo/scene01.svo2.json
```

## 2. SVO/SVO2 with live trajectory sidecars

```bash
make record-svo-pose SESSION=scene01_pose
```

Output:

```text
data/svo/scene01_pose.svo2
data/svo/scene01_pose_trajectory_tum.txt
data/svo/scene01_pose_trajectory.csv
```

## 3. Export RGB-D and poses

```bash
make export-rgbd SVO=data/svo/scene01_pose.svo2
```

Output:

```text
data/rgbd/scene01_pose/rgb/*.png
data/rgbd/scene01_pose/depth_png/*.png
data/rgbd/scene01_pose/depth_npy/*.npy
data/rgbd/scene01_pose/trajectory_tum.txt
data/rgbd/scene01_pose/poses.csv
```

Depth PNG is uint16 millimeters. NPY depth is float32 meters.
