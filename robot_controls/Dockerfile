FROM osrf/ros:humble-desktop

# Install dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3-colcon-common-extensions \
        python3-pip \
        ros-humble-moveit \
        ros-humble-moveit-ros-visualization \
        ros-humble-robot-state-publisher \
        ros-humble-joint-state-publisher-gui \
        ros-humble-xacro \
        ros-humble-rosbag2 \
        ros-humble-rosbag2-py \
    && rm -rf /var/lib/apt/lists/*

RUN pip3 install --no-cache-dir st3215 rich

WORKDIR /ws

# Copy source code
COPY . /ws/src/robot_controls/
COPY ros2/ /ws/src/robot_control/
COPY app/ /ws/app/

# Build packages
RUN . /opt/ros/humble/setup.sh && \
    cd /ws && \
    colcon build --packages-select robot_control robot_controls 2>&1 || true

# Remove source to avoid shadowing
RUN rm -rf /ws/src

ENV ROS_DOMAIN_ID=42
ENV PYTHONPATH="/ws/app"

COPY --chmod=755 <<'EOF' /entrypoint.sh
#!/bin/bash
set -e
source /opt/ros/humble/setup.bash
source /ws/install/setup.bash
export PYTHONPATH="/ws/app:${PYTHONPATH}"

echo "=== robot_controls container ==="
echo "Run: ros2 run robot_controls robot_controls_node --ros-args -p port:=/dev/ttyACM0"

exec "$@"
EOF

ENTRYPOINT ["/entrypoint.sh"]
CMD ["/bin/bash"]
