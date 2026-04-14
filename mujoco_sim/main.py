#!/usr/bin/env python3
"""
MuJoCo Robot Simulation — точка входа.

Режимы:
    (без флагов)        Интерактивная симуляция с viewer
    --mirror            Sim-to-real: реальный робот повторяет симуляцию
    --mirror real_to_sim   Real-to-sim: симуляция отображает реального робота
    --headless          Без viewer (для RL-обучения)

Примеры:
    python main.py
    python main.py --mirror --port COM3
    python main.py --mirror --port COM3 --speed 400 --rate 25
    python main.py --mirror real_to_sim --port /dev/ttyUSB0
    python main.py --mirror --port COM3 --transport ros2
    python main.py --headless
"""

import sys
import os

# Добавляем src/ в путь поиска
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="MuJoCo ST3215 Robot Simulation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--mirror",
        nargs="?",
        const="sim_to_real",
        choices=["sim_to_real", "real_to_sim"],
        metavar="MODE",
        help="Enable mirroring. MODE: sim_to_real (default) | real_to_sim",
    )
    parser.add_argument("--port",      default="COM3",       help="Serial port for real robot")
    parser.add_argument("--baudrate",  default=1_000_000, type=int)
    parser.add_argument("--transport", default="serial", choices=["serial", "ros2"])
    parser.add_argument("--rate",  default=20.0, type=float, help="Mirror rate Hz")
    parser.add_argument("--speed", default=300,  type=int,   help="Motor speed (50-3400)")
    parser.add_argument("--no-safety", action="store_true",  help="Disable angle safety clamping")
    parser.add_argument("--dry-run",   action="store_true",  help="Mirror without real robot")
    parser.add_argument("--headless",  action="store_true",  help="Run without viewer (RL mode)")
    args = parser.parse_args()

    if args.mirror is not None:
        # ── Режим зеркалирования ─────────────────────────────────────
        # Делегируем в run_mirror.py, передавая уже разобранные аргументы
        _run_mirror_mode(args)
    elif args.headless:
        # ── Headless режим (RL) ───────────────────────────────────────
        from mujoco_robot_sim import MuJoCoRobotController, generate_robot_mjcf
        print("Headless mode (Ctrl+C для остановки)")
        xml = generate_robot_mjcf()
        ctrl = MuJoCoRobotController(xml)
        try:
            while True:
                ctrl.step(10)
        except KeyboardInterrupt:
            pass
        finally:
            ctrl.close()
    else:
        # ── Интерактивный режим с viewer ─────────────────────────────
        from mujoco_robot_sim import run_interactive
        run_interactive()


def _run_mirror_mode(args) -> None:
    """Запуск режима зеркалирования (sim ↔ real)."""
    import mujoco
    import mujoco.viewer
    import threading
    import logging

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    from mujoco_robot_sim import MuJoCoRobotController, generate_robot_mjcf
    from mujoco_robot_sim.sim_to_real import SimToRealMirror

    mode = args.mirror  # "sim_to_real" | "real_to_sim"

    print(f"\n  MuJoCo ↔ ST3215 Mirror  [{mode}]")
    print(f"  Port: {args.port}  Rate: {args.rate} Гц  Speed: {args.speed}")
    print(f"  Transport: {args.transport}  Dry-run: {args.dry_run}\n")

    xml = generate_robot_mjcf(with_gripper=True, with_table=True)
    ctrl = MuJoCoRobotController(xml)
    ctrl.set_joint_angles([0.0] * 6, immediate=True)

    mirror: SimToRealMirror | None = None
    if not args.dry_run:
        mirror = SimToRealMirror(
            ctrl,
            mode=mode,
            transport=args.transport,
            port=args.port,
            baudrate=args.baudrate,
            rate_hz=args.rate,
            motor_speed=args.speed,
            safety_check=not args.no_safety,
        )
        if not mirror.start():
            print(f"\n  [!] Не удалось подключиться к {args.port}.")
            print("      Добавьте --dry-run для работы без робота.\n")
            sys.exit(1)
        print(f"  ✓ Зеркало запущено\n")

    viewer = mujoco.viewer.launch_passive(ctrl.model, ctrl.data)
    running = True

    def cmd_loop() -> None:
        nonlocal running
        while running:
            try:
                cmd = input("mirror> ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                running = False
                break
            if cmd in ("q", "quit"):
                running = False
            elif cmd.startswith("angles "):
                try:
                    angles = [float(x) for x in cmd.split()[1:]]
                    ctrl.set_joint_angles(angles)
                except ValueError:
                    pass
            elif cmd == "home":
                ctrl.set_joint_angles([0.0] * 6)
            elif cmd == "stats" and mirror:
                print(" ", mirror.stats)
            elif cmd.startswith("speed ") and mirror:
                mirror.set_motor_speed(int(cmd.split()[1]))
            elif cmd.startswith("goto "):
                parts = cmd.split()
                if len(parts) == 4:
                    ctrl.move_to_point(float(parts[1]), float(parts[2]), float(parts[3]))
            elif cmd == "help":
                print("  angles <j0..j5> | home | goto <x y z> | speed <n> | stats | q")

    threading.Thread(target=cmd_loop, daemon=True).start()

    try:
        while running and viewer.is_running():
            mujoco.mj_step(ctrl.model, ctrl.data)
            viewer.sync()
    except KeyboardInterrupt:
        pass
    finally:
        running = False
        if mirror:
            mirror.stop()
        viewer.close()


if __name__ == "__main__":
    main()
