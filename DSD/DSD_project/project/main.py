#!/usr/bin/env python3
"""
DSD - Defensive Security Dashboard
===================================
Entry point for the application.

Usage:
    python main.py

Author: DSD Project
License: MIT
"""

import sys
import os

# Ensure the project root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from dsd.ui.main_window import MainWindow
from dsd.core.database import DatabaseManager
from dsd.utils.theme import ThemeManager


def main() -> None:
    """Initialize and launch the DSD application."""
    # High-DPI support
    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")

    app = QApplication(sys.argv)
    app.setApplicationName("DSD - Defensive Security Dashboard")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("DSD Project")

    # Default font
    font = QFont("Segoe UI", 10)
    app.setFont(font)

    # Initialize database
    db = DatabaseManager()
    db.initialize()

    # Apply theme (reads saved preference)
    theme_mgr = ThemeManager(app)
    theme_mgr.apply_saved_theme()

    # Launch main window
    window = MainWindow(db=db, theme_manager=theme_mgr)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
