#!/usr/bin/env python3
"""
MuJoCo Robot Simulation — точка входа.
"""

import logging
import math
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))


def _test_serial_port(port: str, baudrate: int) -> bool:
    """Прямая проверка COM-порта без зависимости от контроллера."""
    try:
        import serial

        logger = logging.getLogger("port_test")
        ser = serial.Serial(port, baudrate, timeout=1.0)
        ser.reset_input_buffer()
        # Простой пинг: отправка байта и ожидание ответа
        ser.write(b"\xff")
        time.sleep(0.1)
        data = ser.read(10)
        ser.close()
        logger.info("Порт %s доступен. Ответ: %s", port, data.hex())
        return True
    except Exception as e:
        logging.getLogger("port_test").error("Ошибка доступа к %s: %s", port, e)
        return False


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
    parser.add_argument("--port", default="COM3", help="Serial port for real robot")
    parser.add_argument("--baudrate", default=1_000_000, type=int)
    parser.add_argument("--transport", default="serial", choices=["serial", "ros2"])
    parser.add_argument("--rate", default=20.0, type=float, help="Mirror rate Hz")
    parser.add_argument("--speed", default=300, type=int, help="Motor speed (50-3400)")
    parser.add_argument("--no-safety", action="store_true", help="Disable angle safety clamping")
    parser.add_argument("--dry-run", action="store_true", help="Mirror without real robot")
    parser.add_argument("--headless", action="store_true", help="Run without viewer (RL mode)")
    parser.add_argument("--test-port", action="store_true", help="Test serial port and exit")
    parser.add_argument(
        "--home-pos",
        type=float,
        nargs=6,
        default=[0.0] * 6,
        help="Physical home position in degrees [J0 J1 J2 J3 J4 J5]",
    )
    parser.add_argument(
        "--offsets",
        type=float,
        nargs=6,
        default=[0.0] * 6,
        help="Joint calibration offsets in degrees",
    )
    args = parser.parse_args()

    if args.test_port:
        ok = _test_serial_port(args.port, args.baudrate)
        print(f"{'✅' if ok else '❌'} Порт {args.port} {'доступен' if ok else 'недоступен'}")
        return

    if args.mirror is not None:
        _run_mirror_mode(args)
    elif args.headless:
        from mujoco_robot_sim import MuJoCoRobotController, generate_robot_mjcf

        print("Headless mode (Ctrl+C для остановки)")
        xml = generate_robot_mjcf(with_gripper=True, with_table=True)
        ctrl = MuJoCoRobotController(xml)
        try:
            while True:
                ctrl.step(10)
        except KeyboardInterrupt:
            pass
        finally:
            ctrl.close()
    else:
        from mujoco_robot_sim import run_interactive

        run_interactive()


def _run_mirror_mode(args) -> None:
    import threading

    import mujoco
    import mujoco.viewer

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    from mujoco_robot_sim import MuJoCoRobotController, generate_robot_mjcf
    from mujoco_robot_sim.sim_to_real import SimToRealMirror

    mode = args.mirror
    print(f"\n  MuJoCo ↔ ST3215 Mirror  [{mode}]")
    print(f"  Port: {args.port}  Rate: {args.rate} Гц  Speed: {args.speed}")
    print(f"  Transport: {args.transport}  Dry-run: {args.dry_run}")
    print(f"  Home pos: {args.home_pos}  Offsets: {args.offsets}\n")

    xml = generate_robot_mjcf(with_gripper=True, with_table=True)
    ctrl = MuJoCoRobotController(xml)

    # 🔥 КРИТИЧНО: явно задаём начальную позу симуляции под физическое состояние
    ctrl.data.qpos[:6] = [math.radians(a) for a in args.home_pos]
    ctrl.set_joint_angles([0.0] * 6, immediate=True)

    mirror = None
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
            joint_offsets_deg=args.offsets,
        )
        if not mirror.start():
            print(f"\n  [!] Не удалось подключиться к {args.port}.")
            print("      Проверьте кабель, номер порта и добавьте --test-port для диагностики.")
            print("      Или используйте --dry-run для работы без робота.\n")
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
            elif cmd.startswith("offset ") and mirror:
                try:
                    idx, val = cmd.split()[1:]
                    offsets = list(mirror.stats.get("offsets_deg", [0.0] * 6))
                    offsets[int(idx)] = float(val)
                    mirror.set_offsets(offsets)
                except (ValueError, IndexError):
                    pass
            elif cmd.startswith("goto "):
                parts = cmd.split()
                if len(parts) == 4:
                    ctrl.move_to_point(float(parts[1]), float(parts[2]), float(parts[3]))
            elif cmd == "help":
                print(
                    "  angles <j0..j5> | home | goto <x y z> | speed <n> | offset <idx deg> | stats | q"
                )

    threading.Thread(target=cmd_loop, daemon=True).start()

    try:
        while running and viewer.is_running():
            if mirror and mode == "real_to_sim":
                angles_deg = mirror.poll_real_angles()
                if angles_deg is not None:
                    ctrl.data.qpos[:6] = [math.radians(a) for a in angles_deg]

            mujoco.mj_step(ctrl.model, ctrl.data)
            viewer.sync()

    except KeyboardInterrupt:
        pass
    finally:
        running = False
        if mirror:
            mirror.stop()
        viewer.close()
        ctrl.close()


if __name__ == "__main__":
    main()
