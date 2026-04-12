# ROS2 Topics Makefile for robot_control package
# Usage: make <target>

# Package name
PACKAGE := robot_control

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
	@echo "Targets:"
	@echo "  make list-topics       - List all active topics"
	@echo "  make topic-info        - Show info for robot topics"
	@echo "  make echo-joints       - Echo joint_states topic"
	@echo "  make echo-status       - Echo status topic"
	@echo "  make pub-cmd           - Publish single joint command"
	@echo "  make pub-cmd-all       - Publish all 6 joints command"
	@echo "  make stop              - Send emergency stop"
	@echo "  make run-robot         - Run robot_node_v2"
	@echo "  make run-monitor       - Run monitor_node_v2"
	@echo "  make run-all           - Run both nodes"
	@echo "  make clean             - Clean build artifacts"
	@echo ""
	@echo "Variables:"
	@echo "  PORT=COM3    - Serial port (default: COM3)"
	@echo ""
	@echo "Examples:"
	@echo "  make pub-cmd-all POSITIONS='[0.0, 0.5, 1.0, -0.5, 0.3, 0.0]'"
	@echo "  make run-robot PORT=COM5"
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
