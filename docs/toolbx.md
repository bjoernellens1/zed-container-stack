# Toolbox path

The toolbox image is a Fedora helper shell with Podman, OpenCV, build tools, and the repo scripts. It is mainly useful for fallback work and development.

```bash
make toolbox-build
make toolbox-create
toolbox enter zed-fedora-stack
```

The official ZED SDK itself should still be run from the Ubuntu-based Stereolabs image through Docker/Podman, not installed into the Fedora toolbox.
