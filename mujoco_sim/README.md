# mujoco_sim — MuJoCo Simulation for ST3215 Robot

Physics-based simulation of a 6-DOF ST3215 servo manipulator in MuJoCo 3.x.
Supports interactive control, RL training, and bidirectional sync with the real robot.

---

## Features

- Procedural MJCF generation from DH-parameters (synced with kinematics module)
- Sim-to-real and real-to-sim mirroring over serial (RS-485) or ROS2
- Gymnasium-compatible RL environment with RGB/depth observations
- Interactive viewer with terminal command interface
- Keyboard teleoperation for imitation learning data collection
- Docker support (headless and GUI profiles)

---

## Project Structure

```
mujoco_sim/
├── main.py                         # Entry point (all modes)
├── pyproject.toml                  # Project metadata
├── requirements.txt                # Python dependencies
├── Dockerfile                      # Container build
├── docker-compose.yml              # Service profiles
│
├── src/
│   └── mujoco_robot_sim/
│       ├── __init__.py             # Core API: MuJoCoRobotController, RobotEnv, generate_robot_mjcf
│       └── sim_to_real.py          # SimToRealMirror — background sync thread
│
├── scripts/
│   ├── run_mirror.py               # Standalone mirror launcher (extended CLI)
│   ├── run.sh                      # Linux/macOS launch helper
│   └── run.bat                     # Windows launch helper
│
├── ml/
│   ├── agents/
│   │   ├── base_agent.py           # Abstract RL agent (BaseAgent)
│   │   └── __init__.py             # Exports: BaseAgent, PPOAgent, DQNAgent
│   ├── environments/
│   │   ├── base_robot_env.py       # Gymnasium base environment (BaseRobotEnv)
│   │   ├── lerobot_env.py          # LeRobot data-format environment (LeRobotEnv)
│   │   └── __init__.py             # Exports: BaseRobotEnv, LeRobotEnv
│   ├── models/
│   │   └── robot_generator.py      # MJCF generation from robot_config.json
│   └── stl_models/
│       └── README.md               # STL asset guidelines
│
├── mldataset/
│   └── teleoperation.py            # Keyboard teleoperation (KeyboardTeleop)
│
├── models/                         # Binary STL meshes (robot links)
│   ├── основание.stl               # Base
│   ├── плечо1.stl                  # Shoulder 1
│   ├── плечо2.stl                  # Shoulder 2
│   ├── локоть.stl                  # Elbow
│   ├── кисть1.stl                  # Wrist 1
│   └── кисть2.stl                  # Wrist 2 / gripper
│
└── test/
    └── main.py                     # Test entry point
```

---

## Prerequisites

- Python 3.12+
- MuJoCo 3.0+ (`pip install mujoco`)
- For real robot: `st3215` package and RS-485 adapter

Install all dependencies:

```bash
pip install -r requirements.txt
```

---

## Quick Start

### Interactive viewer (default)

```bash
python main.py
```

Opens the MuJoCo viewer. Use the mouse to rotate/zoom and the terminal for commands:

```
angles <j0..j5>   — set joint angles (degrees)
home              — move to home position
goto <x> <y> <z>  — IK to point (mm)
grip open|close   — gripper control
ee                — print end-effector position
reset             — reset simulation
q                 — quit
```

### Sim-to-real mirroring (sim controls real robot)

```bash
python main.py --mirror --port COM3
# Linux:
python main.py --mirror --port /dev/ttyUSB0
```

The real robot mirrors every joint move made in the simulation.

### Real-to-sim (real robot pose fed into simulation)

```bash
python main.py --mirror real_to_sim --port COM3
```

Useful for recording demonstration trajectories for imitation learning.

### Headless mode (RL training)

```bash
python main.py --headless
```

Runs physics at maximum speed without a viewer window.

---

## CLI Reference

```
python main.py [OPTIONS]

Options:
  --mirror [sim_to_real|real_to_sim]
                        Enable mirroring. Default mode: sim_to_real
  --port PORT           Serial port for real robot (default: COM3)
  --baudrate BAUDRATE   Serial baudrate (default: 1000000)
  --transport {serial,ros2}
                        Communication transport (default: serial)
  --rate RATE           Mirror rate in Hz (default: 20.0)
  --speed SPEED         Motor speed 50–3400 (default: 300)
  --no-safety           Disable joint angle safety clamping
  --dry-run             Run mirror without real robot connected
  --headless            Run without viewer (for RL)
```

### Extended mirror launcher

`scripts/run_mirror.py` provides additional controls (pause/resume, rate adjustment, statistics):

```bash
python scripts/run_mirror.py --port COM3 --mode sim_to_real --rate 30 --speed 400
python scripts/run_mirror.py --dry-run   # test without hardware
```

Additional commands available in this mode:
```
speed <N>     — change motor speed (50–3400)
rate <N>      — change mirror frequency (Hz)
pause         — suspend mirroring
resume        — resume mirroring
stats         — show sync statistics
```

---

## Python API

### Core controller

```python
from mujoco_robot_sim import MuJoCoRobotController, generate_robot_mjcf

xml = generate_robot_mjcf(with_gripper=True, with_table=True, with_objects=True)
ctrl = MuJoCoRobotController(xml)

# Joint control
ctrl.set_joint_angles([0, -30, 60, -30, 0, 0])  # degrees
ctrl.step_seconds(1.0)

angles = ctrl.get_joint_angles()          # → list[float], degrees
ee     = ctrl.get_ee_position_mm()        # → (x, y, z), mm

# IK
ctrl.move_to_point(150, 0, 100)           # mm

# Gripper
ctrl.open_gripper()
ctrl.close_gripper()

# Camera render
rgb = ctrl.render_camera("front")         # → np.ndarray (H, W, 3)

ctrl.close()
```

### Gymnasium RL environment

```python
from mujoco_robot_sim import RobotEnv
import numpy as np

env = RobotEnv()
obs, info = env.reset()

# Action: [j0, j1, j2, j3, j4, j5, gripper] — angles in degrees, gripper 0/1
action = np.array([0, -20, 40, -20, 0, 0, 0], dtype=np.float32)
obs, reward, terminated, truncated, info = env.step(action)

# Observation keys: rgb, depth, joint_angles, ee_pos, gripper_open, object_positions
print(obs["joint_angles"])   # (6,)
print(obs["ee_pos"])         # (3,)
print(obs["rgb"].shape)      # (480, 640, 3)

env.close()
```

### Sim-to-real mirror (programmatic)

```python
from mujoco_robot_sim import MuJoCoRobotController, generate_robot_mjcf
from mujoco_robot_sim.sim_to_real import SimToRealMirror

ctrl = MuJoCoRobotController(generate_robot_mjcf())
mirror = SimToRealMirror(
    ctrl,
    mode="sim_to_real",    # or "real_to_sim"
    transport="serial",    # or "ros2"
    port="COM3",
    rate_hz=20.0,
    motor_speed=300,
)
mirror.start()

ctrl.set_joint_angles([0, -30, 60, -30, 0, 0])

print(mirror.stats)   # {"commands_sent": N, "errors": N, "actual_rate_hz": N}
mirror.stop()
```

### MJCF generation

```python
from mujoco_robot_sim import generate_robot_mjcf

xml = generate_robot_mjcf(
    with_gripper=True,   # two-finger gripper joints + actuators
    with_objects=True,   # red/green/yellow cubes, blue cylinder on table
    with_table=True,     # 300×300×50 mm work surface
    with_cameras=True,   # top_down, front, side, eye_in_hand cameras
)
# xml is a valid MJCF string ready for mujoco.MjModel.from_xml_string(xml)
```

---

## RL / LeRobot Integration

```python
from ml.environments import LeRobotEnv
import numpy as np

env = LeRobotEnv(
    camera_width=256,
    camera_height=256,
    frame_skip=5,
    max_episode_length=500,
)
obs, info = env.reset()

# Observation keys: "observation.state" (6,), "observation.image" (H, W, 3)
print(obs["observation.state"])   # EE pos (xyz) + orientation (rpy)
print(obs["observation.image"].shape)

# Action: (7,) — joint angles + gripper
action = np.zeros(7, dtype=np.float32)
obs, reward, terminated, truncated, info = env.step(action)
env.close()
```

For keyboard teleoperation and dataset recording:

```python
from mldataset.teleoperation import KeyboardTeleop

teleop = KeyboardTeleop(delta_position=0.01, delta_rotation=0.05)
# W/S: X-axis, A/D: Y-axis, R/F: Z-axis, Q/E: roll, SPACE: gripper, Z: reset
```

---

## Docker

### Headless (default)

```bash
docker-compose up
```

### GUI (requires X11 or VcXsrv on Windows)

```bash
docker-compose --profile gui up
```

### Build only

```bash
docker build -t mujoco-sim .
docker run --rm mujoco-sim --headless
```

---

## Robot Kinematics

DH-parameters (synchronized with `app/models/kinematics.py`):

| Joint   | Axis | Range         | Link length |
|---------|------|---------------|-------------|
| joint_0 | Z    | ±120°         | L0 = 19 mm  |
| joint_1 | Y    | −45°…+90°     | L1 = 104 mm |
| joint_2 | Y    | −90°…+45°     | L2 = 95 mm  |
| joint_3 | Y    | −120°…0°      | L3 = 34 mm  |
| joint_4 | Z    | ±90°          | L4 = 35 mm  |
| joint_5 | Y    | ±90°          | —           |

Physics: timestep = 0.002 s (500 Hz), integrator = `implicitfast`, position actuators with kp = 50→20 N·m/rad.

---

## Dependencies

| Package       | Version    | Purpose                        |
|---------------|------------|--------------------------------|
| mujoco        | ≥ 3.0.0   | Physics engine                 |
| numpy         | ≥ 1.24.0  | Numerical computing            |
| st3215        | ≥ 0.1.0   | Real robot communication       |
| pyserial      | ≥ 3.5     | RS-485 serial transport        |
| rclpy         | —          | ROS2 transport (optional)      |
| gymnasium     | —          | RL environment API (optional)  |
| pytest        | —          | Testing                        |
