# ROS2 Topics Makefile for robot_control package
# Usage: make <target>

# Package name
PACKAGE := robot_control

# Docker settings
IMAGE_NAME := robot_control_dev
CONTAINER_NAME := robot_control_container

# Detect OS and USB device
ifeq ($(OS),Windows_NT)
    # Windows - use privileged mode + USB device mapping
    USB_DEVICE ?= /dev/ttyUSB0
    USB_FLAG := --privileged -v /dev/bus/usb:/dev/bus/usb
else
    # Linux/Mac - /dev/ttyUSB0 or similar
    USB_DEVICE ?= /dev/ttyUSB0
    USB_FLAG := --device=$(USB_DEVICE):$(USB_DEVICE)
endif

# Default COM port
PORT ?= COM3

# ROS2 topics from robot_node_v2
TOPICS := \
	/robot/joint_states \
	/robot/joint_cmd \
	/robot/status \
	/robot/stop \
	/robot/diagnostics \
	/robot/temperature \
	/robot/alarms

# Default bag path
BAG_PATH ?= robot_bag_$(shell date +%Y%m%d_%H%M%S)

# ============================================
# HELP
# ============================================
.PHONY: help
help:
	@echo ""
	@echo "ROS2 Topics Makefile for $(PACKAGE)"
	@echo "=================================="
	@echo ""
	@echo "Topics:"
	@echo "  /robot/joint_states  (pub) - current joint positions (JointState)"
	@echo "  /robot/joint_cmd     (sub) - target joint command (JointTrajectoryPoint)"
	@echo "  /robot/status        (pub) - robot status JSON (String)"
	@echo "  /robot/stop          (sub) - emergency stop (Empty)"
	@echo ""
	@echo "Basic targets:"
	@echo "  make list-topics       - List all active topics"
	@echo "  make echo-joints       - Echo joint_states topic"
	@echo "  make pub-cmd-all       - Publish joint command (home position)"
	@echo "  make stop              - Emergency stop"
	@echo ""
	@echo "Docker targets:"
	@echo "  make docker-build      - Build Docker image"
	@echo "  make docker-run        - Run container (interactive)"
	@echo "  make docker-shell      - Shell with full ROS2 env"
	@echo "  make docker-robot      - Run robot_node_v2 in container"
	@echo "  make docker-tui        - Run terminal UI in container"
	@echo "  make docker-all        - Run robot + TUI together"
	@echo "  make docker-exec       - Shell into running container"
	@echo "  make docker-stop       - Emergency stop"
	@echo "  make docker-clean      - Stop container"
	@echo "  make list-usb          - Show USB devices"
	@echo ""
	@echo "Variables:"
	@echo "  USB_DEVICE=COM3        - USB device (default: COM3)"
	@echo "  POSITIONS='[...]'      - Joint positions"
	@echo "  BAG_PATH=my_session    - Bag output directory"
	@echo ""
	@echo "Rosbag2 targets:"
	@echo "  make record            - Record robot topics to bag (auto-named)"
	@echo "  make bag-record        - Record using bag_recorder node"
	@echo "  make bag-play BAG_PATH=<dir> - Play back a recorded bag"
	@echo "  make bag-info BAG_PATH=<dir> - Show bag metadata"
	@echo "  make bag-list          - List .db3 bag files in current dir"
	@echo ""
	@echo "ros2_control targets:"
	@echo "  make run-ros2-control  - Launch full ros2_control stack"
	@echo "  make run-bridge        - Run ros2_control bridge only"
	@echo "  make ctl-list          - List active controllers"
	@echo "  make ctl-interfaces    - List hardware interfaces"
	@echo "  make send-trajectory   - Send example JointTrajectory"
	@echo ""
	@echo "Quick start:"
	@echo "  1. make docker-build"
	@echo "  2. make docker-all     # robot + TUI"
	@echo ""
	@echo "TUI controls: j/J=select joint, a/z=move, h=home, r=ready, s=stop, q=quit"
	@echo ""

# ============================================
# TOPIC INFO
# ============================================
.PHONY: list-topics
list-topics:
	@echo "Active topics:"
	@ros2 topic list

.PHONY: topic-info
topic-info:
	@echo "Robot topics info:"
	@for topic in $(TOPICS); do \
		echo ""; \
		echo "=== $$topic ==="; \
		ros2 topic info $$topic 2>/dev/null || echo "Topic not found"; \
	done

# ============================================
# ECHO (Subscribe)
# ============================================
.PHONY: echo-joints
echo-joints:
	ros2 topic echo /robot/joint_states

.PHONY: echo-status
echo-status:
	ros2 topic echo /robot/status

.PHONY: echo-cmd
echo-cmd:
	ros2 topic echo /robot/joint_cmd

.PHONY: echo-all
echo-all: echo-joints
# Note: Run in separate terminals for multiple echoes

# ============================================
# PUBLISH Commands
# ============================================
# Default positions (6 joints in radians)
POSITIONS ?= [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]

.PHONY: pub-cmd
pub-cmd:
	@ros2 topic pub --once /robot/joint_cmd trajectory_msgs/JointTrajectoryPoint \
		"{positions: $(POSITIONS)}"

# Publish all 6 joints
.PHONY: pub-cmd-all
pub-cmd-all:
	@echo "Publishing joint command: $(POSITIONS)"
	@ros2 topic pub --once /robot/joint_cmd trajectory_msgs/JointTrajectoryPoint \
		"{positions: $(POSITIONS), velocities: [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]}"

# Home position
.PHONY: pub-home
pub-home:
	@echo "Moving to home position..."
	@ros2 topic pub --once /robot/joint_cmd trajectory_msgs/JointTrajectoryPoint \
		"{positions: [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]}"

# Ready position (arm extended forward)
.PHONY: pub-ready
pub-ready:
	@echo "Moving to ready position..."
	@ros2 topic pub --once /robot/joint_cmd trajectory_msgs/JointTrajectoryPoint \
		"{positions: [0.0, -0.5, 0.8, 0.0, 0.5, 0.0]}"

# ============================================
# EMERGENCY STOP
# ============================================
.PHONY: stop
stop:
	@echo "Sending emergency stop!"
	@ros2 topic pub --once /robot/stop std_msgs/Empty "{}"

# ============================================
# RUN NODES
# ============================================
.PHONY: run-robot
run-robot:
	ros2 run $(PACKAGE) robot_node_v2 --ros-args -p port:=$(PORT)

.PHONY: run-monitor
run-monitor:
	ros2 run $(PACKAGE) monitor_node_v2

.PHONY: run-all
run-all:
	@echo "Starting robot_node_v2 on $(PORT)..."
	@ros2 launch $(PACKAGE) robot_v2.launch.py port:=$(PORT)

# ============================================
# SIMPLE LAUNCH (make run)
# ============================================
.PHONY: run
run:
	@echo "Launching robot_node_v2 and kinematics_node..."
	@export PYTHONPATH=../core:$$PYTHONPATH && \
	ros2 run robot_control robot_node_v2 --ros-args -p port:=$(PORT) & \
	sleep 2 && \
	ros2 run robot_control kinematics_node & \
	sleep 1 && \
	echo "Nodes started. Use 'make control' to interact or 'make check' to verify."

# ============================================
# CHECK TOPICS (make check)
# ============================================
.PHONY: check
check:
	@echo "=== Active Nodes ==="
	ros2 node list
	@echo "\n=== Active Topics ==="
	ros2 topic list
	@echo "\n=== Topic Rates (3s) ==="
	timeout 3 ros2 topic hz /robot/joint_states || true
	@echo "\n=== Kinematics Pose Topic ==="
	ros2 topic info /robot/target_pose 2>/dev/null || echo "Start kinematics_node to see /robot/target_pose"

# ============================================
# CONTROL VIA TOPICS (make control)
# ============================================
.PHONY: control
control:
	@echo "Starting TUI for control..."
	python3 $(CURDIR)/robot_tui.py

.PHONY: pub-pose
pub-pose:
	@echo "Publishing target pose (0.2m, 0.0, 0.3m)..."
	ros2 topic pub --once /robot/target_pose geometry_msgs/PoseStamped \
		"{header: {frame_id: 'base_link'}, pose: {position: {x: 0.2, y: 0.0, z: 0.3}, orientation: {w: 1.0}}"

# ============================================
# BUILD & INSTALL
# ============================================
.PHONY: build
build:
	@echo "Building $(PACKAGE)..."
	cd .. && colcon build --packages-select $(PACKAGE)

.PHONY: install
install: build
	@source ../install/setup.bash && colcon build --packages-select $(PACKAGE)

.PHONY: clean
clean:
	@echo "Cleaning build artifacts..."
	@rm -rf build/ install/ log/
	@echo "Done."

# ============================================
# ROSBAG2
# ============================================

# Record via ros2 bag CLI (простой вариант)
.PHONY: record
record:
	@echo "Recording to $(BAG_PATH)..."
	@ros2 bag record -o $(BAG_PATH) $(TOPICS)

# Record via bag_recorder node (запускает все узлы + запись)
.PHONY: bag-record
bag-record:
	@echo "Starting bag_recorder node (bag_path=$(BAG_PATH))..."
	@ros2 launch $(PACKAGE) record_bag.launch.py \
		port:=$(PORT) bag_path:=$(BAG_PATH)

# Playback a bag
.PHONY: bag-play
bag-play:
	@if [ -z "$(BAG_PATH)" ]; then \
		echo "Usage: make bag-play BAG_PATH=<directory>"; exit 1; \
	fi
	@echo "Playing back: $(BAG_PATH)"
	@ros2 bag play $(BAG_PATH) \
		--topics $(TOPICS)

# Show bag info
.PHONY: bag-info
bag-info:
	@if [ -z "$(BAG_PATH)" ]; then \
		echo "Usage: make bag-info BAG_PATH=<directory>"; exit 1; \
	fi
	@ros2 bag info $(BAG_PATH)

# List bag files
.PHONY: bag-list
bag-list:
	@echo "Bag files in current directory:"
	@find . -name "*.db3" -o -name "metadata.yaml" 2>/dev/null | head -40 || \
		echo "No bag files found"

# ============================================
# ROS2_CONTROL
# ============================================

# Launch full ros2_control stack
.PHONY: run-ros2-control
run-ros2-control:
	@echo "Starting ros2_control stack on $(PORT)..."
	@ros2 launch $(PACKAGE) ros2_control.launch.py port:=$(PORT)

# Run bridge node only (assumes controller_manager already running)
.PHONY: run-bridge
run-bridge:
	ros2 run $(PACKAGE) ros2_control_bridge --ros-args -p port:=$(PORT)

# List controllers
.PHONY: ctl-list
ctl-list:
	@ros2 control list_controllers

# List hardware interfaces
.PHONY: ctl-interfaces
ctl-interfaces:
	@ros2 control list_hardware_interfaces

# Send example trajectory to JointTrajectoryController
.PHONY: send-trajectory
send-trajectory:
	@echo "Sending example trajectory (all joints → 0.5 rad)..."
	@ros2 action send_goal /joint_trajectory_controller/follow_joint_trajectory \
		control_msgs/action/FollowJointTrajectory \
		"{ \
		  trajectory: { \
		    joint_names: [joint_0, joint_1, joint_2, joint_3, joint_4, joint_5], \
		    points: [{ \
		      positions: [0.5, 0.5, 0.5, 0.5, 0.5, 0.5], \
		      time_from_start: {sec: 2, nanosec: 0} \
		    }] \
		  } \
		}"

# ============================================
# DEVELOPMENT
# ============================================
.PHONY: bw
bw:
	@echo "Bandwidth usage:"
	@for topic in $(TOPICS); do \
		ros2 topic bw $$topic 2>/dev/null || true; \
	done

.PHONY: hz
hz:
	@echo "Topic hz:"
	@for topic in $(TOPICS); do \
		echo ""; \
		echo "=== $$topic ==="; \
		ros2 topic hz $$topic 2>/dev/null || echo "Topic not active"; \
	done

# ============================================
# DOCKER
# ============================================

# --network host is required on Linux so multiple containers share ROS2 DDS discovery.
# On Mac/Windows Docker Desktop uses a VM and host networking doesn't work the same way —
# for those platforms use docker-all-single which runs everything in one container.
NETWORK_FLAG := --network host

.PHONY: docker-build
docker-build:
	@echo "Building Docker image $(IMAGE_NAME)..."
	@bash build_docker.sh

# Interactive shell inside a container (with USB + host network)
.PHONY: docker-run
docker-run:
	@echo "Starting container (host network + USB)..."
	docker run -it --rm \
		--name $(CONTAINER_NAME) \
		--network host \
		-e ROS_DOMAIN_ID=42 \
		$(USB_FLAG) \
		$(IMAGE_NAME)

# Run with full privileged USB access
.PHONY: docker-run-usb
docker-run-usb:
	@echo "Starting container with full USB access..."
	docker run -it --rm \
		--name $(CONTAINER_NAME) \
		--network host \
		--privileged \
		-v /dev/bus/usb:/dev/bus/usb \
		$(IMAGE_NAME)

# Shell into a running container
.PHONY: docker-exec
docker-exec:
	docker exec -it $(CONTAINER_NAME) bash

# Run robot node inside an already-running container
.PHONY: docker-robot
docker-robot:
	docker exec -it $(CONTAINER_NAME) \
		bash -c "source /opt/ros/humble/setup.bash && \
		         source /ws/install/setup.bash && \
		         ros2 run robot_control robot_node_v2 --ros-args -p port:=$(USB_DEVICE)"

# List active topics from a running container
.PHONY: docker-topics
docker-topics:
	docker exec $(CONTAINER_NAME) bash -c \
		"source /opt/ros/humble/setup.bash && ros2 topic list"

# Echo a topic (usage: make docker-echo TOPIC=/robot/joint_states)
.PHONY: docker-echo
docker-echo:
	docker exec -it $(CONTAINER_NAME) bash -c \
		"source /opt/ros/humble/setup.bash && ros2 topic echo $(TOPIC)"

# Publish a joint command from outside the container
.PHONY: docker-pub
docker-pub:
	docker exec $(CONTAINER_NAME) bash -c \
		"source /opt/ros/humble/setup.bash && \
		ros2 topic pub --once /robot/joint_cmd trajectory_msgs/JointTrajectoryPoint \
		'{positions: $(POSITIONS)}'"

# Emergency stop from outside the container
.PHONY: docker-stop
docker-stop:
	docker exec $(CONTAINER_NAME) bash -c \
		"source /opt/ros/humble/setup.bash && \
		ros2 topic pub --once /robot/stop std_msgs/Empty '{}'"

# Stop and remove container
.PHONY: docker-clean
docker-clean:
	docker stop $(CONTAINER_NAME) 2>/dev/null || true
	docker rm   $(CONTAINER_NAME) 2>/dev/null || true

# Stop all containers related to this project
.PHONY: stop-all
stop-all:
	@echo "Stopping all robot_control containers..."
	@docker ps -a --filter "name=robot_control" --format "{{.Names}}" | while read container; do \
		echo "Stopping $$container..."; \
		docker stop $$container 2>/dev/null || true; \
		docker rm   $$container 2>/dev/null || true; \
	done
	@echo "Done."

# ============================================
# INTERACTIVE (TUI)
# ============================================

# ── RECOMMENDED for Ubuntu ──────────────────────────────────────────────────
# Starts robot_node_v2 in background INSIDE the same container, then launches TUI.
# Both share the same ROS2 context — no networking required.
.PHONY: docker-all
docker-all:
	@echo "Starting robot + TUI in a single container (USB_DEVICE=$(USB_DEVICE))..."
	docker run -it --rm \
		--name $(CONTAINER_NAME) \
		--network host \
		--privileged \
		-v /dev/bus/usb:/dev/bus/usb \
		-v $(CURDIR)/../core:/ws/core \
		-e ROS_DOMAIN_ID=42 \
		-e PYTHONPATH=/ws/core:/ws/app:$$PYTHONPATH \
		$(IMAGE_NAME) bash -c "\
			source /opt/ros/humble/setup.bash && \
			source /ws/install/setup.bash && \
			ros2 run robot_control robot_node_v2 \
			    --ros-args -p port:=$(USB_DEVICE) & \
			sleep 2 && \
			python3 /ws/robot_tui.py"

# TUI only (assumes robot_node_v2 is running in another terminal/container on host network)
.PHONY: docker-tui
docker-tui:
	@echo "Starting TUI (connects to robot on host network)..."
	docker run -it --rm \
		--name $(CONTAINER_NAME)-tui \
		--network host \
		-e ROS_DOMAIN_ID=42 \
		$(IMAGE_NAME) bash -c "\
			source /opt/ros/humble/setup.bash && \
			source /ws/install/setup.bash && \
			export PYTHONPATH=/ws/app:\$$PYTHONPATH && \
			python3 /ws/robot_tui.py"

# Robot node only (background container, host network)
.PHONY: docker-robot-bg
docker-robot-bg:
	@echo "Starting robot node in background container..."
	docker run -d --rm \
		--name $(CONTAINER_NAME)-robot \
		--network host \
		--privileged \
		-v /dev/bus/usb:/dev/bus/usb \
		-e ROS_DOMAIN_ID=42 \
		$(IMAGE_NAME) bash -c "\
			source /opt/ros/humble/setup.bash && \
			source /ws/install/setup.bash && \
			ros2 run robot_control robot_node_v2 \
			    --ros-args -p port:=$(USB_DEVICE)"
	@echo "Robot node running in background. Now run: make docker-tui"

# Interactive shell with full ROS2 env
.PHONY: docker-shell
docker-shell:
	@echo "Starting interactive shell..."
	docker run -it --rm \
		--name $(CONTAINER_NAME)-shell \
		--network host \
		--privileged \
		-v /dev/bus/usb:/dev/bus/usb \
		-e ROS_DOMAIN_ID=42 \
		$(IMAGE_NAME) bash

# ============================================
# GAZEBO SIMULATION
# ============================================
#
# Требования (установить один раз):
#   sudo apt install ros-humble-gazebo-ros-pkgs \
#                    ros-humble-gazebo-ros2-control
#
# Gazebo запускается только нативно (не в Docker без X11).

# Запустить Gazebo с примитивами-цилиндрами (без STL)
.PHONY: gazebo
gazebo:
	@echo "Launching Gazebo simulation (cylinder primitives)..."
	ros2 launch robot_control gazebo.launch.py

# Запустить Gazebo с mesh-моделями (нужны STL в meshes/)
.PHONY: gazebo-meshes
gazebo-meshes:
	@echo "Launching Gazebo with mesh visuals..."
	ros2 launch robot_control gazebo.launch.py use_meshes:=true

# Запустить Gazebo с кастомным миром
.PHONY: gazebo-world
gazebo-world:
	@if [ -z "$(WORLD)" ]; then echo "Usage: make gazebo-world WORLD=/path/to/my.world"; exit 1; fi
	ros2 launch robot_control gazebo.launch.py world:=$(WORLD)

# HOME позиция в симуляции (через JTC action)
.PHONY: gazebo-home
gazebo-home:
	@echo "Sending HOME position to simulated robot..."
	ros2 action send_goal /joint_trajectory_controller/follow_joint_trajectory \
		control_msgs/action/FollowJointTrajectory \
		"{ trajectory: { \
		     joint_names: [joint_0, joint_1, joint_2, joint_3, joint_4, joint_5], \
		     points: [{ \
		       positions: [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], \
		       time_from_start: {sec: 2, nanosec: 0} \
		     }] \
		   } }"

# READY позиция в симуляции
.PHONY: gazebo-ready
gazebo-ready:
	@echo "Sending READY position to simulated robot..."
	ros2 action send_goal /joint_trajectory_controller/follow_joint_trajectory \
		control_msgs/action/FollowJointTrajectory \
		"{ trajectory: { \
		     joint_names: [joint_0, joint_1, joint_2, joint_3, joint_4, joint_5], \
		     points: [{ \
		       positions: [0.0, -0.5, 0.8, 0.0, 0.5, 0.0], \
		       time_from_start: {sec: 3, nanosec: 0} \
		     }] \
		   } }"

# Проверить топики симуляции
.PHONY: gazebo-topics
gazebo-topics:
	@echo "Gazebo simulation topics:"
	@ros2 topic list | grep -E "(joint|controller|gazebo)" || echo "No active topics"

# Список контроллеров в симуляции
.PHONY: gazebo-controllers
gazebo-controllers:
	ros2 control list_controllers

# Установить Gazebo зависимости (выполнить один раз)
.PHONY: gazebo-install-deps
gazebo-install-deps:
	@echo "Installing Gazebo ROS packages..."
	sudo apt update && sudo apt install -y \
		ros-humble-gazebo-ros-pkgs \
		ros-humble-gazebo-ros2-control \
		ros-humble-gazebo-plugins \
		ros-humble-rviz2

# Show USB devices
.PHONY: list-usb
list-usb:
	@echo "USB devices:"
	@ifneq ($(OS),Windows_NT)
		ls -la /dev/ttyUSB* /dev/ttyACM* 2>/dev/null || echo "No USB serial devices found"
	else
		powershell -Command "Get-PnpDevice -PresentOnly | Where-Object { \$$_.InstanceId -match '^USB' }"
	endif
