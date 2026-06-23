"""
dsd/ui/main_window.py
======================
Main application window for DSD.

Hosts the left-side navigation and the central tab/page area.
All pages are loaded as tabs in a QTabWidget.
"""

import logging
from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QPushButton, QLabel, QStatusBar, QTabWidget,
    QSizePolicy, QSpacerItem, QFrame,
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QFont, QIcon

from dsd.ui.pages.dashboard import DashboardPage
from dsd.ui.pages.scanner import ScannerPage
from dsd.ui.pages.capture import CapturePage
from dsd.ui.pages.recommendations import RecommendationsPage
from dsd.ui.pages.history import HistoryPage
from dsd.ui.pages.settings import SettingsPage

if TYPE_CHECKING:
    from dsd.core.database import DatabaseManager
    from dsd.utils.theme import ThemeManager

logger = logging.getLogger(__name__)


class NavButton(QPushButton):
    """Sidebar navigation button."""

    def __init__(self, icon: str, label: str, parent: QWidget | None = None) -> None:
        super().__init__(f"  {icon}  {label}", parent)
        self.setCheckable(True)
        self.setFixedHeight(44)
        self.setFont(QFont("Segoe UI", 11))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("""
            QPushButton {
                text-align: left;
                padding-left: 16px;
                border: none;
                border-radius: 6px;
                background: transparent;
                font-weight: normal;
            }
            QPushButton:checked {
                background-color: rgba(137,180,250,0.18);
                font-weight: bold;
            }
            QPushButton:hover:!checked {
                background-color: rgba(137,180,250,0.08);
            }
        """)


class Sidebar(QFrame):
    """
    Left-side navigation panel.

    Emits page index changes via ``page_requested`` callbacks.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedWidth(210)
        self.setObjectName("card")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 16, 10, 16)
        layout.setSpacing(4)

        # App logo / title
        logo = QLabel("🛡 DSD")
        logo.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        logo.setStyleSheet("color: #89b4fa; background: transparent; padding: 4px 8px;")
        layout.addWidget(logo)

        subtitle = QLabel("Defensive Security\nDashboard")
        subtitle.setFont(QFont("Segoe UI", 9))
        subtitle.setStyleSheet("color: #6c7086; background: transparent; padding: 0 8px 12px;")
        layout.addWidget(subtitle)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #313244;")
        layout.addWidget(sep)
        layout.addSpacing(8)

        # Nav buttons
        self._buttons: list[NavButton] = []

        pages = [
            ("🏠", "Dashboard"),
            ("🔍", "Network Scanner"),
            ("📦", "Packet Capture"),
            ("🔒", "Recommendations"),
            ("📋", "History"),
            ("⚙", "Settings"),
        ]

        self._callbacks: list = []

        for icon, label in pages:
            btn = NavButton(icon, label)
            self._buttons.append(btn)
            layout.addWidget(btn)

        layout.addStretch()

        # Version label
        ver = QLabel("v1.0.0")
        ver.setFont(QFont("Segoe UI", 8))
        ver.setStyleSheet("color: #585b70; background: transparent; padding: 4px 8px;")
        layout.addWidget(ver)

        # Connect buttons
        for idx, btn in enumerate(self._buttons):
            btn.clicked.connect(lambda checked, i=idx: self._on_nav(i))

        # Select first by default
        self._buttons[0].setChecked(True)

    def set_page_callback(self, callback) -> None:
        self._page_callback = callback

    def _on_nav(self, index: int) -> None:
        for i, btn in enumerate(self._buttons):
            btn.setChecked(i == index)
        if hasattr(self, "_page_callback"):
            self._page_callback(index)

    def select(self, index: int) -> None:
        self._on_nav(index)


class MainWindow(QMainWindow):
    """
    Top-level application window.

    Owns the sidebar navigation and the stacked page area.
    """

    def __init__(
        self,
        db: "DatabaseManager",
        theme_manager: "ThemeManager",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._db = db
        self._theme = theme_manager
        theme_manager.set_db(db)

        self.setWindowTitle("DSD — Defensive Security Dashboard")
        self.setMinimumSize(1100, 700)
        self.resize(1280, 780)

        self._build_ui()
        self._status("Ready")

    # ------------------------------------------------------------------ #
    #  UI construction                                                      #
    # ------------------------------------------------------------------ #

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Sidebar
        self._sidebar = Sidebar()
        self._sidebar.set_page_callback(self._navigate)
        root.addWidget(self._sidebar)

        # Main content area
        content_wrapper = QWidget()
        content_layout = QVBoxLayout(content_wrapper)
        content_layout.setContentsMargins(16, 16, 16, 8)
        content_layout.setSpacing(0)

        # Pages (stacked via QTabWidget with tabs hidden)
        self._pages = QTabWidget()
        self._pages.tabBar().setVisible(False)  # navigation is via sidebar

        # Instantiate pages
        self._dashboard = DashboardPage(db=self._db, navigate_cb=self._navigate)
        self._scanner = ScannerPage(db=self._db, status_cb=self._status)
        self._capture = CapturePage(db=self._db, status_cb=self._status)
        self._recs = RecommendationsPage(db=self._db)
        self._history = HistoryPage(db=self._db)
        self._settings = SettingsPage(db=self._db, theme_manager=self._theme)

        for page in (
            self._dashboard,
            self._scanner,
            self._capture,
            self._recs,
            self._history,
            self._settings,
        ):
            self._pages.addTab(page, "")

        content_layout.addWidget(self._pages, 1)
        root.addWidget(content_wrapper, 1)

        # Status bar
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status("DSD ready — scan only authorized systems.")

    # ------------------------------------------------------------------ #
    #  Navigation                                                           #
    # ------------------------------------------------------------------ #

    def _navigate(self, index: int) -> None:
        """Switch to the page at *index*."""
        self._pages.setCurrentIndex(index)
        self._sidebar.select(index)
        # Refresh data when switching to certain pages
        if index == 0:
            self._dashboard.refresh()
        elif index == 3:
            self._recs.refresh()
        elif index == 4:
            self._history.refresh()

    # ------------------------------------------------------------------ #
    #  Status bar                                                           #
    # ------------------------------------------------------------------ #

    def _status(self, message: str, timeout: int = 0) -> None:
        """Update the status bar message."""
        self._status_bar.showMessage(message, timeout)
