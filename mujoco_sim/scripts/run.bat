@echo off
REM MuJoCo Robot Simulation Launcher for Windows
REM Supports both headless and GUI modes

setlocal enabledelayedexpansion

cd "%~dp0\.."

if "%~1"=="" goto headless
if /i "%~1"=="gui" goto gui
if /i "%~1"=="headless" goto headless
if /i "%~1"=="build" goto build
if /i "%~1"=="test" goto test
if /i "%~1"=="shell" goto shell
if /i "%~1"=="clean" goto clean
if /i "%~1"=="-h" goto help
if /i "%~1"=="--help" goto help

echo Unknown mode: %~1
goto help

:help
echo MuJoCo Robot Simulation Launcher
echo.
echo Usage: run.bat [MODE]
echo.
echo Modes:
echo   gui         Launch with GUI (requires VcXsrv or similar X server)
echo   headless    Launch in headless mode (default)
echo   build       Build Docker image
echo   test        Run unit tests
echo   shell       Open shell in container
echo   clean       Remove containers and images
echo   -h, --help  Show this help message
echo.
echo Examples:
echo   run.bat gui       # Launch GUI mode
echo   run.bat headless  # Launch headless mode
echo   run.bat test      # Run tests
exit /b 1

:build
echo Building Docker image...
docker-compose build --no-cache
echo Build complete!
exit /b 0

:gui
echo Launching GUI mode...
echo.
echo NOTE: You need an X server installed and running!
echo   - VcXsrv: https://sourceforge.net/projects/vcxsrv/
echo   - Xming: https://sourceforge.net/projects/xming/
echo.
echo Make sure to: 
echo   1. Start the X server
echo   2. Allow connections from remote hosts
echo.
pause
docker-compose run --rm --service-ports mujoco-gui
exit /b 0

:headless
echo Launching headless mode...
docker-compose run --rm mujoco-headless
exit /b 0

:test
echo Running tests...
docker-compose run --rm mujoco-headless python -m pytest tests/ -v
exit /b 0

:shell
echo Opening shell in container...
docker-compose run --rm mujoco-headless bash
exit /b 0

:clean
echo Cleaning up...
docker-compose down --remove-orphans
docker-compose rm -f
docker rmi mujoco_sim_mujoco-sim 2> NUL
echo Cleanup complete!
exit /b 0
