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
.PHONY: docker-build
docker-build:
	@echo "Building Docker image $(IMAGE_NAME)..."
	@bash build_docker.sh

.PHONY: docker-run
docker-run:
	@echo "Starting container..."
	docker run -it --rm \
		--name $(CONTAINER_NAME) \
		-e ROS_DOMAIN_ID=42 \
		$(USB_FLAG) \
		$(IMAGE_NAME)

# Run with full USB access
.PHONY: docker-run-usb
docker-run-usb:
	@echo "Starting container with USB access..."
	docker run -it --rm \
		--name $(CONTAINER_NAME) \
		--privileged \
		-v /dev/bus/usb:/dev/bus/usb \
		$(IMAGE_NAME)

# Docker exec into running container
.PHONY: docker-exec
docker-exec:
	docker exec -it $(CONTAINER_NAME) bash

# Run robot node in Docker
.PHONY: docker-robot
docker-robot:
	docker exec -it $(CONTAINER_NAME) \
		bash -c "source /opt/ros/humble/setup.bash && \
		         source /ws/install/setup.bash && \
		         ros2 run robot_control robot_node_v2 --ros-args -p port:=$(USB_DEVICE)" || \
	docker exec -it $(CONTAINER_NAME)-robot \
		bash -c "source /opt/ros/humble/setup.bash && \
		         source /ws/install/setup.bash && \
		         ros2 run robot_control robot_node_v2 --ros-args -p port:=$(USB_DEVICE)"

# Docker - list topics
.PHONY: docker-topics
docker-topics:
	docker exec $(CONTAINER_NAME) bash -c "source /opt/ros/humble/setup.bash && ros2 topic list"

# Docker - echo topic
.PHONY: docker-echo
docker-echo:
	docker exec -it $(CONTAINER_NAME) bash -c "source /opt/ros/humble/setup.bash && ros2 topic echo $(TOPIC)"

# Docker - publish joint command
.PHONY: docker-pub
docker-pub:
	docker exec $(CONTAINER_NAME) bash -c "source /opt/ros/humble/setup.bash && \
		ros2 topic pub --once /robot/joint_cmd trajectory_msgs/JointTrajectoryPoint \
		'{positions: $(POSITIONS)}'"

# Docker - emergency stop
.PHONY: docker-stop
docker-stop:
	docker exec $(CONTAINER_NAME) bash -c "source /opt/ros/humble/setup.bash && \
		ros2 topic pub --once /robot/stop std_msgs/Empty '{}'"

# Stop and remove container
.PHONY: docker-clean
docker-clean:
	docker stop $(CONTAINER_NAME) 2>/dev/null || true

# Stop all containers related to this project
.PHONY: stop-all
stop-all:
	@echo "Stopping all robot_control containers..."
	@docker ps -a --filter "name=robot_control" --format "{{.Names}}" | while read container; do \
		echo "Stopping $$container..."; \
		docker stop $$container 2>/dev/null || true; \
		docker rm $$container 2>/dev/null || true; \
	done
	@echo "Done."

# ============================================
# INTERACTIVE (TUI)
# ============================================
.PHONY: docker-tui
docker-tui:
	@echo "Starting Robot TUI in container..."
	docker run -it --rm \
		--name $(CONTAINER_NAME) \
		--privileged \
		-v /dev/bus/usb:/dev/bus/usb \
		$(IMAGE_NAME) bash -c "source /opt/ros/humble/setup.bash && \
			source /ws/install/setup.bash && \
			export PYTHONPATH=/ws/app:\$$PYTHONPATH && \
			python3 /ws/robot_tui.py"

# Start robot + TUI together
.PHONY: docker-all
docker-all: docker-robot-bg docker-tui

.PHONY: docker-robot-bg
docker-robot-bg:
	@echo "Starting robot node in background..."
	docker run -d --rm \
		--name $(CONTAINER_NAME)-robot \
		--privileged \
		-v /dev/bus/usb:/dev/bus/usb \
		$(IMAGE_NAME) bash -c "source /opt/ros/humble/setup.bash && \
			source /ws/install/setup.bash && \
			ros2 run robot_control robot_node_v2 --ros-args -p port:=$(USB_DEVICE)"
	@echo "Robot started! Starting TUI..."

.PHONY: docker-shell
docker-shell:
	@echo "Starting interactive shell with full ROS2 environment..."
	docker run -it --rm \
		--name $(CONTAINER_NAME)-shell \
		--privileged \
		-v /dev/bus/usb:/dev/bus/usb \
		$(IMAGE_NAME) bash

# Show USB devices
.PHONY: list-usb
list-usb:
	@echo "USB devices:"
	@ifneq ($(OS),Windows_NT)
		ls -la /dev/ttyUSB* /dev/ttyACM* 2>/dev/null || echo "No USB serial devices found"
	else
		powershell -Command "Get-PnpDevice -PresentOnly | Where-Object { \$$_.InstanceId -match '^USB' }"
	endif
