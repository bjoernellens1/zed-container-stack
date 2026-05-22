# GUI support on Fedora

Use X11/Xwayland for the ZED SDK GUI tools.

```bash
make gui-allow
make viewer
make depth-viewer
```

If windows do not open:

```bash
echo $DISPLAY
xhost
./scripts/host-diagnose.sh
```

For NVIDIA OpenGL inside the container:

```bash
docker compose --profile nvidia-sdk run --rm zed-nvidia-sdk glxinfo -B
```

Close access after use:

```bash
make gui-deny
```
