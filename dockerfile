FROM ros:humble-ros-core

ENV DEBIAN_FRONTEND=noninteractive

# Установка инструментов для сборки и работы с портами
RUN apt-get update && apt-get install -y \
    python3-pip \
    python3-serial \
    python3-colcon-common-extensions \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /ros2_ws

COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

COPY servo_driver_pkg ./src/servo_driver_pkg

RUN source /opt/ros/humble/setup.sh && \
    colcon build --packages-select servo_driver_pkg

ENTRYPOINT ["bash", "-c", "source /opt/ros/humble/setup.bash && source /ros2_ws/install/setup.bash && exec ros2 run servo_driver_pkg servo_driver"]