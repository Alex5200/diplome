#!/bin/bash

# MuJoCo Robot Simulation Launcher
# Supports both headless and GUI modes

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Help message
show_help() {
    echo "MuJoCo Robot Simulation Launcher"
    echo ""
    echo "Usage: $0 [OPTIONS] [MODE]"
    echo ""
    echo "Modes:"
    echo "  gui         Launch with GUI (requires X11)"
    echo "  headless    Launch in headless mode (default)"
    echo "  build       Build Docker image"
    echo "  test        Run unit tests"
    echo "  shell       Open shell in container"
    echo "  clean       Remove containers and images"
    echo ""
    echo "Options:"
    echo "  -h, --help  Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 gui          # Launch GUI mode"
    echo "  $0 headless     # Launch headless mode"
    echo "  $0 build        # Build image"
    echo "  $0 test         # Run tests"
}

# Check if Docker is installed
check_docker() {
    if ! command -v docker &> /dev/null; then
        echo -e "${RED}Error: Docker is not installed${NC}"
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        echo -e "${RED}Error: docker-compose is not installed${NC}"
        exit 1
    fi
}

# Setup X11 permissions for macOS
setup_x11_macos() {
    if [[ "$OSTYPE" == "darwin"* ]]; then
        echo -e "${YELLOW}Setting up X11 for macOS...${NC}"
        
        # Check if XQuartz is installed
        if ! command -v xquartz &> /dev/null && [ ! -d "/Applications/Utilities/XQuartz.app" ]; then
            echo -e "${RED}Error: XQuartz is not installed${NC}"
            echo "Install with: brew install --cask xquartz"
            exit 1
        fi
        
        # Start XQuartz if not running
        if ! pgrep -x "X11-bin" > /dev/null; then
            open -a XQuartz
            sleep 2
        fi
        
        # Allow connections from localhost
        xhost +localhost
        
        # Set DISPLAY for macOS
        export DISPLAY=host.docker.internal:0
    fi
}

# Setup X11 permissions for Linux
setup_x11_linux() {
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        echo -e "${YELLOW}Setting up X11 for Linux...${NC}"
        xhost +local:docker
    fi
}

# Build Docker image
build_image() {
    echo -e "${GREEN}Building Docker image...${NC}"
    cd "$PROJECT_DIR"
    docker-compose build --no-cache
    echo -e "${GREEN}Build complete!${NC}"
}

# Run in GUI mode
run_gui() {
    echo -e "${GREEN}Launching GUI mode...${NC}"
    
    setup_x11_macos
    setup_x11_linux
    
    cd "$PROJECT_DIR"
    docker-compose run --rm --service-ports mujoco-gui
}

# Run in headless mode
run_headless() {
    echo -e "${GREEN}Launching headless mode...${NC}"
    cd "$PROJECT_DIR"
    docker-compose run --rm mujoco-headless
}

# Run tests
run_tests() {
    echo -e "${GREEN}Running tests...${NC}"
    cd "$PROJECT_DIR"
    docker-compose run --rm mujoco-headless python -m pytest tests/ -v
}

# Open shell
run_shell() {
    echo -e "${GREEN}Opening shell in container...${NC}"
    cd "$PROJECT_DIR"
    docker-compose run --rm mujoco-headless bash
}

# Clean up
clean() {
    echo -e "${YELLOW}Cleaning up...${NC}"
    cd "$PROJECT_DIR"
    docker-compose down --remove-orphans
    docker-compose rm -f
    docker rmi mujoco_sim_mujoco-sim 2>/dev/null || true
    echo -e "${GREEN}Cleanup complete!${NC}"
}

# Main
main() {
    check_docker
    
    case "${1:-headless}" in
        -h|--help)
            show_help
            exit 0
            ;;
        gui)
            run_gui
            ;;
        headless)
            run_headless
            ;;
        build)
            build_image
            ;;
        test)
            run_tests
            ;;
        shell)
            run_shell
            ;;
        clean)
            clean
            ;;
        *)
            echo -e "${RED}Unknown mode: $1${NC}"
            show_help
            exit 1
            ;;
    esac
}

main "$@"
