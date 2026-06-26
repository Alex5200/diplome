#!/usr/bin/env python3
"""
Скрипт захвата скриншотов для презентации.

Запуск: python docs/capture_screenshots.py

Инструкция:
1. Запустите приложение: python app/main.py
2. Переключитесь на нужную вкладку
3. Нажмите Enter в этом скрипте для захвата скриншота
"""
import subprocess
import os

OUT_DIR = os.path.join(os.path.dirname(__file__), "diagrams")
os.makedirs(OUT_DIR, exist_ok=True)

tabs = [
    ("screenshot_dashboard.png", "Dashboard — главная панель"),
    ("screenshot_jog.png", "Jog — ручное управление"),
    ("screenshot_3dview.png", "3D View — визуализация кинематики"),
    ("screenshot_registers.png", "Registers — позиционные регистры"),
    ("screenshot_teach.png", "Teach — пульт обучения"),
    ("screenshot_program.png", "Program — блочное программирование"),
    ("screenshot_setup.png", "Setup — настройка моторов"),
    ("screenshot_xyc.png", "XYZ — декартовы координаты"),
    ("screenshot_alarms.png", "Alarms — аварии"),
    ("screenshot_vision.png", "AI Vision — трекинг"),
    ("screenshot_ai_control.png", "AI Control — AI-управление"),
]

print("=" * 60)
print("  Скрипт захвата скриншотов для презентации")
print("=" * 60)
print(f"\nСкриншоты будут сохранены в: {OUT_DIR}")
print("\nИнструкция:")
print("1. Запустите приложение: python app/main.py")
print("2. Разместите окно приложения на видном месте")
print("3. Для каждого скриншота переключитесь на вкладку и нажмите Enter")
print("   (или введите 'n' чтобы пропустить)")
print("   (или 'q' чтобы выйти)")
print()

for filename, description in tabs:
    filepath = os.path.join(OUT_DIR, filename)
    if os.path.exists(filepath):
        resp = input(f"[S] {description} — уже существует, перезаписать? (y/n): ").strip().lower()
        if resp != 'y':
            print("  Пропущено")
            continue

    input(f"[Enter] {description}   ...готово? ")

    result = subprocess.run(
        ["screencapture", "-x", filepath],
        capture_output=True, text=True
    )
    if result.returncode == 0 and os.path.exists(filepath):
        print(f"  ✓ Сохранено: {filename}")
    else:
        print(f"  ✗ Ошибка: {result.stderr}")

print("\nГотово! Скриншоты сохранены в", OUT_DIR)
