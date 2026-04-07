#!/bin/bash
# Скрипт запуска приложения через системный Python (для macOS)
# uv не поддерживает tkinter на macOS из-за отсутствия Tcl/Tk

cd "$(dirname "$0")"

echo "Запуск ST3215 Robot Control через системный Python..."
echo "Python: $(which python3)"
echo "Tcl/Tk: $(python3 -c 'import tkinter; print(tkinter.Tcl().eval(\"info patchlevel\"))' 2>/dev/null || echo 'не найден')"
echo "=================================="

python3 app/main.py
