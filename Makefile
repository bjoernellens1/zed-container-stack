SHELL := /usr/bin/env bash
COMPOSE ?= docker compose
PROFILE ?= nvidia-sdk
SERVICE ?= zed-nvidia-tools
SESSION ?= $$(date +%Y%m%d_%H%M%S)

.PHONY: help init list-tags gui-allow gui-deny build pull shell viewer depth-viewer diagnostic record-svo record-svo-pose export-rgbd ros2-shell ros2-record opencapture-shell opencapture-viewer podman-nvidia toolbox-build toolbox-create toolbox-enter

help:
	@sed -n '1,220p' README.md | sed -n '/^## Quick start/,$$p' | head -n 120

init:
	@cp -n .env.example .env || true
	@mkdir -p data/{svo,rgbd,rosbags,logs,calibration}
	@echo "Created .env and data directories. Edit .env to choose a valid stereolabs/zed tag."

list-tags:
	@./scripts/list-zed-tags.sh

gui-allow:
	@./scripts/gui-allow.sh

gui-deny:
	@./scripts/gui-deny.sh

pull:
	@$(COMPOSE) --profile $(PROFILE) pull || true

build:
	@$(COMPOSE) --profile $(PROFILE) build

shell:
	@$(COMPOSE) --profile $(PROFILE) run --rm $(SERVICE) bash

viewer:
	@./scripts/gui-allow.sh
	@$(COMPOSE) --profile nvidia-sdk run --rm zed-nvidia-sdk bash -lc '/usr/local/zed/tools/ZED_Explorer'

depth-viewer:
	@./scripts/gui-allow.sh
	@$(COMPOSE) --profile nvidia-sdk run --rm zed-nvidia-sdk bash -lc '/usr/local/zed/tools/ZED_Depth_Viewer'

diagnostic:
	@$(COMPOSE) --profile nvidia-sdk run --rm zed-nvidia-sdk bash -lc '/usr/local/zed/tools/ZED_Diagnostic -c || python3 /workspace/tools/zed_system_check.py'

record-svo:
	@$(COMPOSE) --profile nvidia-sdk run --rm zed-nvidia-sdk bash -lc 'python3 /workspace/tools/zed_record_svo.py --out /data/svo/$(SESSION).svo2 --duration "$${ZED_RECORD_SECONDS:-0}" --resolution "$${ZED_RESOLUTION:-HD720}" --fps "$${ZED_FPS:-30}" --depth-mode "$${ZED_DEPTH_MODE:-NEURAL_LIGHT}"'

record-svo-pose:
	@$(COMPOSE) --profile nvidia-sdk run --rm zed-nvidia-sdk bash -lc 'python3 /workspace/tools/zed_record_svo.py --out /data/svo/$(SESSION).svo2 --trajectory /data/svo/$(SESSION)_trajectory_tum.txt --trajectory-csv /data/svo/$(SESSION)_trajectory.csv --duration "$${ZED_RECORD_SECONDS:-0}" --resolution "$${ZED_RESOLUTION:-HD720}" --fps "$${ZED_FPS:-30}" --depth-mode "$${ZED_DEPTH_MODE:-NEURAL_LIGHT}" --enable-tracking'

export-rgbd:
	@test -n "$(SVO)" || (echo "Usage: make export-rgbd SVO=data/svo/file.svo2" && exit 2)
	@$(COMPOSE) --profile nvidia-sdk run --rm zed-nvidia-sdk bash -lc 'python3 /workspace/tools/zed_export_rgbd_trajectory.py --svo /$(SVO) --out /data/rgbd/$$(basename "$(SVO)" .svo2) --with-trajectory --depth-png --depth-npy'

ros2-shell:
	@$(COMPOSE) --profile nvidia-ros2 run --rm zed-nvidia-ros2 bash

ros2-record:
	@$(COMPOSE) --profile nvidia-ros2 run --rm zed-nvidia-ros2 bash -lc '/workspace/scripts/ros2-record.sh /data/rosbags/$(SESSION)'

opencapture-shell:
	@$(COMPOSE) --profile cpu run --rm zed-cpu-opencapture bash

opencapture-viewer:
	@./scripts/gui-allow.sh
	@$(COMPOSE) --profile cpu run --rm zed-cpu-opencapture bash -lc 'zed_open_capture_video_example'

podman-nvidia:
	@./scripts/podman-nvidia-run.sh bash

toolbox-build:
	@$(COMPOSE) --profile toolbx-image build zed-toolbox-image

toolbox-create:
	@./scripts/toolbox-create.sh

toolbox-enter:
	@toolbox enter zed-fedora-stack
