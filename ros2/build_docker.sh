#!/bin/bash
# Build script for robot_control Docker image
# Build context is parent dir with app/ and ros2/ as siblings

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PARENT_DIR="$(dirname "$SCRIPT_DIR")"

echo "Building robot_control_dev Docker image..."
echo "Source: $SCRIPT_DIR"
echo "Parent: $PARENT_DIR"

# Create temp directory for build context
TEMP_DIR=$(mktemp -d)
echo "Temp dir: $TEMP_DIR"
trap 'rm -rf "$TEMP_DIR"' EXIT

# Copy app from parent (for hardware_interface imports)
echo "Copying app from $PARENT_DIR/app to $TEMP_DIR/app"
cp -r "$PARENT_DIR/app" "$TEMP_DIR/app/"

# Copy ros2 package as "ros2" in temp (matches dockerfile COPY paths)
echo "Copying ros2 from $SCRIPT_DIR to $TEMP_DIR/ros2"
cp -r "$SCRIPT_DIR" "$TEMP_DIR/ros2/"

echo ""
echo "Build context structure:"
ls -la "$TEMP_DIR/"
ls -la "$TEMP_DIR/ros2/"

# Build Docker image from temp root (where app and ros2 are siblings)
docker build -t robot_control_dev -f "$TEMP_DIR/ros2/dockerfile" "$TEMP_DIR"

echo ""
echo "========================================"
echo "Build complete!"
echo "Image: robot_control_dev"
echo "========================================"
echo ""
echo "Next steps:"
echo "  make docker-run     - Run container (interactive)"
echo "  make docker-shell   - Shell with ROS2 env"
echo "  make docker-tui     - Terminal UI"
echo ""
