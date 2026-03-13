"""
ui/dialogs.py - modal dialogs

Dialogs:
    PassphraseDialog   - ask for passphrase (open existing file)
    NewPassphraseDialog - ask for passphrase + confirm (new file / save as)
"""

from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QFormLayout, QLabel,
    QLineEdit, QVBoxLayout, QMessageBox,
)
from PySide6.QtCore import Qt


class PassphraseDialog(QDialog):
    """Single passphrase input - used when opening an existing file."""

    def __init__(self, parent=None, filename: str = ''):
        super().__init__(parent)
        self.setWindowTitle("Open File")
        self.setMinimumWidth(360)

        layout = QVBoxLayout(self)

        if filename:
            layout.addWidget(QLabel(f"File: {filename}"))

        form = QFormLayout()
        self._passphrase_edit = QLineEdit()
        self._passphrase_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._passphrase_edit.setPlaceholderText("Enter passphrase")
        form.addRow("Passphrase:", self._passphrase_edit)
        layout.addLayout(form)

        self._open_buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self._open_buttons.accepted.connect(self.accept)
        self._open_buttons.rejected.connect(self.reject)
        layout.addWidget(self._open_buttons)

        self._open_ok = self._open_buttons.button(QDialogButtonBox.StandardButton.Ok)
        self._open_ok.setEnabled(False)
        self._passphrase_edit.textChanged.connect(self._update_open_ok_enabled)
        self._passphrase_edit.returnPressed.connect(self._on_open_return)

    def _update_open_ok_enabled(self) -> None:
        self._open_ok.setEnabled(bool(self._passphrase_edit.text().strip()))

    def _on_open_return(self) -> None:
        if self._open_ok.isEnabled():
            self.accept()

    def passphrase(self) -> str:
        return self._passphrase_edit.text()


class NewPassphraseDialog(QDialog):
    """Passphrase + confirmation - used for new file or Save As."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Set Passphrase")
        self.setMinimumWidth(360)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            "Set a passphrase for this file.\n"
            "Warning: if you forget the passphrase, the data cannot be recovered."
        ))

        form = QFormLayout()

        self._passphrase_edit = QLineEdit()
        self._passphrase_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._passphrase_edit.setPlaceholderText("Enter passphrase")
        form.addRow("Passphrase:", self._passphrase_edit)

        self._confirm_edit = QLineEdit()
        self._confirm_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._confirm_edit.setPlaceholderText("Re-enter passphrase")
        form.addRow("Confirm:", self._confirm_edit)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._confirm_edit.returnPressed.connect(self._on_accept)

    def _on_accept(self):
        if not self._passphrase_edit.text():
            QMessageBox.warning(self, "Error", "Passphrase cannot be empty.")
            return
        if self._passphrase_edit.text() != self._confirm_edit.text():
            QMessageBox.warning(self, "Error", "Passphrases do not match.")
            self._confirm_edit.clear()
            self._confirm_edit.setFocus()
            return
        self.accept()

    def passphrase(self) -> str:
        return self._passphrase_edit.text()
