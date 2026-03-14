"""
main.py - Page application entry point

Installs a global exception hook so uncaught errors show a dialog instead of
silently terminating (important when distributed as exe).
"""

import os
import sys
import traceback

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMessageBox

import crypto
from ui.dialogs import apply_window_icon
from main_window import MainWindow
from version import __version__


def _install_excepthook() -> None:
    """After QApplication exists, uncaught exceptions show a message box."""
    _orig = sys.excepthook

    def excepthook(exc_type, exc_value, exc_tb):
        traceback.print_exception(exc_type, exc_value, exc_tb)
        app = QApplication.instance()
        if app is not None:
            try:
                m = QMessageBox()
                m.setIcon(QMessageBox.Icon.Critical)
                m.setWindowTitle("Unexpected error")
                m.setText(
                    f"{exc_type.__name__}: {exc_value}\n\n"
                    "Details were printed to the console if available."
                )
                apply_window_icon(m)
                m.exec()
            except Exception:
                pass
        else:
            _orig(exc_type, exc_value, exc_tb)

    sys.excepthook = excepthook


def _app_icon_path() -> str:
    if getattr(sys, "frozen", False):
        return os.path.join(sys._MEIPASS, "page.ico")
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui", "page.ico")


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Page")
    app.setApplicationVersion(__version__)
    _ip = _app_icon_path()
    _ic = QIcon(_ip) if os.path.isfile(_ip) else QIcon()
    if not _ic.isNull():
        app.setWindowIcon(_ic)
    _install_excepthook()

    if not crypto.age_bundle_ready():
        QMessageBox.critical(
            None,
            "age not found",
            "Cannot encrypt without age.\n\n" + crypto.age_bundle_help_text(),
        )
        sys.exit(1)

    try:
        window = MainWindow()
        if not _ic.isNull():
            window.setWindowIcon(_ic)
        window.show()
        # Command line: Page.exe "path\to\file.page" (association will use exe)
        if len(sys.argv) > 1:
            window.open_initial_file(sys.argv[1])
    except Exception:
        traceback.print_exc()
        m = QMessageBox()
        m.setIcon(QMessageBox.Icon.Critical)
        m.setWindowTitle("Startup error")
        m.setText(f"Could not start application:\n{sys.exc_info()[1]}")
        apply_window_icon(m)
        m.exec()
        sys.exit(1)

    sys.exit(app.exec())


if __name__ == '__main__':
    main()
