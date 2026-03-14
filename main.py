"""
main.py - Page application entry point

Installs a global exception hook so uncaught errors show a dialog instead of
silently terminating (important when distributed as exe).
"""

import sys
import traceback

from PySide6.QtWidgets import QApplication, QMessageBox
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
                QMessageBox.critical(
                    None,
                    "Unexpected error",
                    f"{exc_type.__name__}: {exc_value}\n\n"
                    "Details were printed to the console if available.",
                )
            except Exception:
                pass
        else:
            _orig(exc_type, exc_value, exc_tb)

    sys.excepthook = excepthook


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Page")
    app.setApplicationVersion(__version__)
    _install_excepthook()

    try:
        window = MainWindow()
        window.show()
    except Exception:
        traceback.print_exc()
        QMessageBox.critical(
            None,
            "Startup error",
            f"Could not start application:\n{sys.exc_info()[1]}",
        )
        sys.exit(1)

    sys.exit(app.exec())


if __name__ == '__main__':
    main()
