#!/usr/bin/env python3
"""
run_mirror.py — Запуск MuJoCo симуляции с зеркалированием на реальный робот.

═══════════════════════════════════════════════════════════════════════════════
 РЕЖИМЫ РАБОТЫ
═══════════════════════════════════════════════════════════════════════════════

  sim_to_real (по умолчанию)
      Управляйте роботом в MuJoCo — реальный повторяет движения.
      Используйте мышь/клавиши в viewer или вводите команды в терминал.

  real_to_sim
      Двигайте реального робота руками — симуляция отображает позу.
      Полезно для записи траекторий (датасеты для RL).

═══════════════════════════════════════════════════════════════════════════════
 ИСПОЛЬЗОВАНИЕ
═══════════════════════════════════════════════════════════════════════════════

  python scripts/run_mirror.py --port COM3
  python scripts/run_mirror.py --port /dev/ttyUSB0 --rate 30 --speed 400
  python scripts/run_mirror.py --port COM3 --mode real_to_sim
  python scripts/run_mirror.py --port COM3 --transport ros2
  python scripts/run_mirror.py --dry-run          # без реального робота

═══════════════════════════════════════════════════════════════════════════════
 КОМАНДЫ В ТЕРМИНАЛЕ (во время работы)
═══════════════════════════════════════════════════════════════════════════════

  angles <j0..j5>   — установить углы симуляции (градусы)
  goto <x> <y> <z>  — IK к точке (мм)
  grip open/close   — управление гриппером
  speed <N>         — изменить скорость моторов (50–3400)
  rate <N>          — изменить частоту зеркалирования (Гц)
  stats             — показать статистику
  pause             — приостановить зеркалирование
  resume            — возобновить зеркалирование
  home              — перейти в домашнюю позицию
  reset             — сбросить симуляцию
  q / quit          — выход
"""

from __future__ import annotations

import argparse
import logging
import sys
import os
import threading
import time

# Путь к исходникам проекта
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
_SIM_SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
for p in (_ROOT, os.path.join(_SIM_SRC, "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

import mujoco
import mujoco.viewer

from mujoco_robot_sim import MuJoCoRobotController, generate_robot_mjcf
from mujoco_robot_sim.sim_to_real import SimToRealMirror

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("run_mirror")


# ── Константы ─────────────────────────────────────────────────────────────
HOME_ANGLES = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
STATS_INTERVAL_S = 10.0


# ── Главная функция ────────────────────────────────────────────────────────

def main() -> None:
    args = _parse_args()
    _configure_logging(args.verbose)

    print(_BANNER)

    # ── Симуляция ───────────────────────────────────────────────────────
    xml = generate_robot_mjcf(with_gripper=True, with_table=True, with_objects=True)
    ctrl = MuJoCoRobotController(xml)
    ctrl.set_joint_angles(HOME_ANGLES, immediate=True)
    ctrl.open_gripper()

    print(f"\n  Режим:      {args.mode}")
    print(f"  Транспорт:  {args.transport}")
    if not args.dry_run:
        print(f"  Порт:       {args.port}  ({args.baudrate} бод)")
    print(f"  Частота:    {args.rate} Гц")
    print(f"  Скорость:   {args.speed}")
    print(f"  Dry-run:    {args.dry_run}")
    print()

    # ── Зеркало ─────────────────────────────────────────────────────────
    mirror: SimToRealMirror | None = None
    mirror_paused = False

    if not args.dry_run:
        mirror = SimToRealMirror(
            ctrl,
            mode=args.mode,
            transport=args.transport,
            port=args.port,
            baudrate=args.baudrate,
            rate_hz=args.rate,
            motor_speed=args.speed,
            safety_check=not args.no_safety,
        )
        ok = mirror.start()
        if not ok:
            print(f"\n  [!] Не удалось подключиться к {args.port}.")
            print("      Запустите с --dry-run для работы без реального робота.\n")
            sys.exit(1)

        print(f"  ✓ Зеркало запущено ({args.mode})\n")
    else:
        print("  [dry-run] Зеркало отключено\n")

    # ── Viewer (должен быть в главном потоке) ───────────────────────────
    viewer = mujoco.viewer.launch_passive(ctrl.model, ctrl.data)
    running = True

    # ── Поток терминальных команд ────────────────────────────────────────
    def input_loop() -> None:
        nonlocal running, mirror_paused

        _print_commands()

        while running:
            try:
                cmd = input("mirror> ").strip()
            except (EOFError, KeyboardInterrupt):
                running = False
                break

            if not cmd:
                continue

            parts = cmd.split()
            verb = parts[0].lower()

            try:
                # ── Выход ──────────────────────────────────────────────
                if verb in ("q", "quit", "exit"):
                    running = False

                # ── Управление позами ──────────────────────────────────
                elif verb == "angles" and len(parts) == 7:
                    angles = [float(p) for p in parts[1:]]
                    ctrl.set_joint_angles(angles)
                    _print(f"Углы: {[f'{a:.1f}°' for a in angles]}")

                elif verb == "home":
                    ctrl.set_joint_angles(HOME_ANGLES)
                    _print("Домашняя позиция")

                elif verb == "goto" and len(parts) == 4:
                    x, y, z = float(parts[1]), float(parts[2]), float(parts[3])
                    ctrl.set_target_marker(x, y, z)
                    result = ctrl.move_to_point(x, y, z)
                    if result:
                        _print(f"IK → {[f'{a:.1f}°' for a in result]}")
                    else:
                        _print("IK: точка недостижима")

                elif verb == "grip":
                    action = parts[1].lower() if len(parts) > 1 else "open"
                    if action == "close":
                        ctrl.close_gripper()
                        _print("Gripper: закрыт")
                    else:
                        ctrl.open_gripper()
                        _print("Gripper: открыт")

                elif verb == "reset":
                    ctrl.reset()
                    ctrl.open_gripper()
                    _print("Симуляция сброшена")

                elif verb == "ee":
                    pos = ctrl.get_ee_position_mm()
                    _print(f"EE: ({pos[0]:.1f}, {pos[1]:.1f}, {pos[2]:.1f}) мм")

                # ── Управление зеркалом ────────────────────────────────
                elif verb == "pause" and mirror:
                    mirror._running = False
                    mirror_paused = True
                    _print("Зеркало приостановлено")

                elif verb == "resume" and mirror:
                    if mirror_paused:
                        mirror._running = True
                        mirror._thread = threading.Thread(
                            target=mirror._mirror_loop,
                            name="SimToRealMirror",
                            daemon=True,
                        )
                        mirror._thread.start()
                        mirror_paused = False
                    _print("Зеркало возобновлено")

                elif verb == "speed" and len(parts) == 2 and mirror:
                    mirror.set_motor_speed(int(parts[1]))
                    _print(f"Скорость моторов: {mirror._motor_speed}")

                elif verb == "rate" and len(parts) == 2 and mirror:
                    mirror.set_rate(float(parts[1]))
                    _print(f"Частота: {mirror._rate_hz:.0f} Гц")

                elif verb == "stats":
                    if mirror:
                        s = mirror.stats
                        _print(
                            f"Отправлено: {s['commands_sent']}  "
                            f"Ошибок: {s['errors']}  "
                            f"Пропущено: {s['frames_dropped']}  "
                            f"Реальный ритм: {s['actual_rate_hz']} Гц"
                        )
                    else:
                        _print("Зеркало не запущено (dry-run)")

                elif verb == "help":
                    _print_commands()

                else:
                    _print(f"Неизвестная команда: {cmd!r}. Введите 'help'.")

            except Exception as e:
                _print(f"Ошибка: {e}")

    input_thread = threading.Thread(target=input_loop, daemon=True)
    input_thread.start()

    # ── Поток периодической статистики ──────────────────────────────────
    def stats_loop() -> None:
        while running:
            time.sleep(STATS_INTERVAL_S)
            if mirror and running:
                s = mirror.stats
                logger.info(
                    "Статистика: %d команд, %d ошибок, %.1f Гц",
                    s["commands_sent"], s["errors"], s["actual_rate_hz"],
                )

    threading.Thread(target=stats_loop, daemon=True).start()

    # ── Главный цикл симуляции (главный поток) ──────────────────────────
    try:
        while running and viewer.is_running():
            mujoco.mj_step(ctrl.model, ctrl.data)
            viewer.sync()
    except KeyboardInterrupt:
        pass
    finally:
        running = False
        print("\n  Завершение...")

        if mirror:
            mirror.stop()
            s = mirror.stats
            print(f"\n  Итог: {s['commands_sent']} команд  "
                  f"{s['errors']} ошибок  "
                  f"avg {s['actual_rate_hz']} Гц")

        viewer.close()
        print("  Готово.\n")


# ── Вспомогательные функции ────────────────────────────────────────────────

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="MuJoCo ↔ ST3215 mirror runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--port",      default="COM3",       help="Serial port (default: COM3)")
    p.add_argument("--baudrate",  default=1_000_000, type=int, help="Baudrate")
    p.add_argument("--mode",      default="sim_to_real",
                   choices=["sim_to_real", "real_to_sim"],
                   help="Mirror direction (default: sim_to_real)")
    p.add_argument("--transport", default="serial",
                   choices=["serial", "ros2"],
                   help="Communication transport (default: serial)")
    p.add_argument("--rate",  default=20.0, type=float, help="Mirror rate Hz (default: 20)")
    p.add_argument("--speed", default=300,  type=int,   help="Motor speed 50-3400 (default: 300)")
    p.add_argument("--no-safety",  action="store_true", help="Disable angle safety clamping")
    p.add_argument("--dry-run",    action="store_true", help="Run without real robot")
    p.add_argument("--verbose",    action="store_true", help="Verbose logging")
    return p.parse_args()


def _configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.getLogger("mujoco_robot_sim").setLevel(level)
    logging.getLogger("run_mirror").setLevel(level)


def _print(msg: str) -> None:
    print(f"  {msg}")


def _print_commands() -> None:
    print("""
  Команды:
    angles <j0..j5>   — установить углы (градусы)
    home              — домашняя позиция
    goto <x> <y> <z>  — IK к точке (мм)
    grip open|close   — управление гриппером
    ee                — позиция end-effector
    reset             — сброс симуляции
    ─────────────────────────────────────────
    speed <N>         — скорость моторов (50–3400)
    rate <N>          — частота зеркала (Гц)
    pause / resume    — пауза/продолжение
    stats             — статистика
    ─────────────────────────────────────────
    help              — это меню
    q                 — выход
""")


_BANNER = """
╔══════════════════════════════════════════════════════════╗
║       MuJoCo ↔ ST3215  SIM-TO-REAL  MIRROR              ║
║  Управляйте симуляцией — реальный робот повторяет позу   ║
╚══════════════════════════════════════════════════════════╝"""


if __name__ == "__main__":
    main()
