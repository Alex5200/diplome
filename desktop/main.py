"""
Desktop entry point.
Launches the FANUC-style Tkinter GUI for direct PC control via USB serial.

Usage:
    python desktop/main.py
    python -m desktop.main
"""

import sys
import os

# Ensure project root is on the path so 'app' and 'shared' are importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.main import main

if __name__ == "__main__":
    main()
