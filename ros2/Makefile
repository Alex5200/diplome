# ROS2 Topics Makefile for robot_control package
# Usage: make <target>

# Package name
PACKAGE := robot_control

# Docker settings
IMAGE_NAME := robot_control_dev
CONTAINER_NAME := robot_control_container

# Detect OS and USB device
ifeq ($(OS),Windows_NT)
    # Windows - COM port
    USB_DEVICE ?= COM3
    USB_FLAG := -e ROS_DOMAIN_ID=42
else
    # Linux/Mac - /dev/ttyUSB0 or similar
    USB_DEVICE ?= /dev/ttyUSB0
    USB_FLAG := --device=/dev/ttyUSB0:/dev/ttyUSB0
endif

# Default COM port
PORT ?= COM3

# ROS2 topics from robot_node_v2
TOPICS := \
	/robot/joint_states \
	/robot/joint_cmd \
	/robot/status \
	/robot/stop

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
# DEVELOPMENT
# ============================================
.PHONY: record
record:
	@ros2 bag record -o robot_topics $(TOPICS)

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
	@echo "Starting container with USB device $(USB_DEVICE)..."
	docker run -it --rm \
		--name $(CONTAINER_NAME) \
		$(USB_FLAG) \
		$(USB_DEVICE) \
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
		-v "$(shell pwd)/robot_tui.py:/robot_tui.py" \
		$(IMAGE_NAME) bash -c "source /opt/ros/humble/setup.bash && \
			source /ws/install/setup.bash && \
			python3 /robot_tui.py"

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
