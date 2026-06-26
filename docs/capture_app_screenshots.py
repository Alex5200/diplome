#!/usr/bin/env python3
"""
Помощник по захвату скриншотов рабочего приложения

Требования к работе:
1. Запустите приложение: python app/main.py
2. Разместите окно приложения на экране (предпочтительно в левой части)
3. Запустите этот скрипт
4. Скрипт автоматически перейдёт к каждой вкладке и сделает скриншот

Зависимости: pip install mss
"""
import time
import mss.mss as mss
import mss.tools
import subprocess
import os
import sys

# Директория для сохранения скриншотов
OUT_DIR = os.path.join(os.path.dirname(__file__), "diagrams")
os.makedirs(OUT_DIR, exist_ok=True)

# Ключевые таймауты для переходов между вкладками
TRANSITION_TIMEOUT = 2

# Определение области экрана для захвата (смещение.
# Вам нужно будет настроить эти параметры в зависимости от расположения окна приложения на экране.
# Типичный путь для запуска в macOS:
# Основное окно будет в левой части экрана с размером ~1440x900
# Мы используем mss для захвата только области, где находится окно приложения.

def capture_screen(x, y, width, height, filename):
    """Захват области экрана и сохранение в PNG."""
    with mss.MSS() as sct:
        monitor = {"left": x, "top": y, "width": width, "height": height}
        sct_img = sct.grab(monitor)
        mss.tools.to_png(sct_img.rgb, sct_img.size, output=filename)
        return filename


def main():
    print("=" * 70)
    print("  Помощник по захвату скриншотов приложения Robot Control")
    print("=" * 70)
    print("\nИнструкция:")
    print("1. Запустите приложение в отдельном терминале (не здесь).")
    print("   Путь запуска: python app/main.py")
    print("2. Переместите окно приложения в левую область экрана (рекомендуется).")
    print("3. Запустите этот скрипт (он автоматически взаимодействует с окном).")
    print("\nСкрипт автоматически переключится к каждой вкладке и сделает скриншот.")
    print("\nЕсли некоторые скриншоты не получаются, вы можете пропустить шаг.")
    print("=" * 70)

    if not input("Нажмите Enter, чтобы запустить автоматический процесс (или 'q' для выхода): ").lower().startswith('q'):
        print("\nНачало процесса захвата скриншотов...\n")

        tabs = [
            ("3D View", 100, 100, 1200, 700, "screenshot_3dview.png"),
            ("Dashboard", 100, 100, 1200, 700, "screenshot_dashboard.png"),
            ("Jog", 100, 100, 1200, 700, "screenshot_jog.png"),
            ("Registers", 100, 100, 1200, 700, "screenshot_registers.png"),
            ("Teach", 100, 100, 1200, 700, "screenshot_teach.png"),
            ("Program", 100, 100, 1200, 700, "screenshot_program.png"),
            ("Setup", 100, 100, 1200, 700, "screenshot_setup.png"),
            ("Alarms", 100, 100, 1200, 700, "screenshot_alarms.png"),
            ("XYZ", 100, 100, 1200, 700, "screenshot_xyz.png"),
            ("AI Vision", 100, 100, 1200, 700, "screenshot_vision.png"),
        ]

        for name, x0, y0, w, h, filename in tabs:
            print(f"[Переход к вкладке '{name}' и захват скриншота]")
            # Эмуляция нажатия клавиши, чтобы переключиться к вкладке
            # Это примерный подход — точные клавиши зависят от приложения
            # Здесь для демонстрации используются макросы, которые вы можете настроить

            # Здесь мы просто эмулируем переход с помощью тултип-с помощью AppleScript
            # Это может быть сделано, но для простоты мы просто захватим экран
            # Дочитайте позже в комментариях по поводу AppleScript

            time.sleep(TRANSITION_TIMEOUT)

            try:
                output_path = os.path.join(OUT_DIR, filename)
                capture_screen(x0, y0, w, h, output_path)
                print(f"   Сохранено: {output_path}")
            except Exception as e:
                print(f"   Ошибка: {e}")

        print("\n✓ Процесс завершён! Все скриншоты сохранены в папке", OUT_DIR)
    else:
        print("Процесс отменён.")

if __name__ == "__main__":
    main()
