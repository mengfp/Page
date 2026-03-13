"""
ui/entry_editor.py - right panel: title, tags, content editor with Apply/Cancel

Apply  : writes edited fields into the Entry object, emits entry_changed(entry, True)
Cancel : reverts the editor to the last applied state, emits nothing
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit,
    QPlainTextEdit, QLabel, QFrame, QPushButton,
)
from PySide6.QtCore import Signal, Slot

from store import Entry


class EntryEditorPanel(QWidget):
    entry_changed = Signal(object, bool)  # (Entry, refresh_list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._entry: Entry | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        form = QFormLayout()

        # Title
        self._title_edit = QLineEdit()
        self._title_edit.setPlaceholderText("Title")
        form.addRow("Title:", self._title_edit)

        # Tags (comma-separated)
        self._tags_edit = QLineEdit()
        self._tags_edit.setPlaceholderText("tag1, tag2, tag3")
        form.addRow("Tags:", self._tags_edit)

        # Modified (read-only)
        self._modified_label = QLabel()
        form.addRow("Modified:", self._modified_label)

        layout.addLayout(form)

        # Separator
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(line)

        # Content editor
        self._content_edit = QPlainTextEdit()
        self._content_edit.setPlaceholderText("Content...")
        layout.addWidget(self._content_edit, 1)

        # Apply / Cancel buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._apply_btn = QPushButton("Apply")
        # clicked(bool) — accept checked so PySide never confuses overloads with other slots
        self._apply_btn.clicked.connect(self._on_apply)
        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.clicked.connect(self._on_cancel)
        btn_row.addWidget(self._apply_btn)
        btn_row.addWidget(self._cancel_btn)
        layout.addLayout(btn_row)

        self._set_enabled(False)

    def set_entry(self, entry: Entry | None) -> None:
        """Display the given entry. Pass None to clear the editor."""
        self._entry = entry
        if entry is None:
            self._title_edit.clear()
            self._tags_edit.clear()
            self._modified_label.clear()
            self._content_edit.clear()
            self._set_enabled(False)
        else:
            self._load_from_entry(entry)
            self._set_enabled(True)

    def refresh_modified(self) -> None:
        """Refresh the modified timestamp display after a save."""
        if self._entry is not None:
            self._modified_label.setText(
                self._entry.modified.astimezone().strftime('%Y-%m-%d %H:%M')
            )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _load_from_entry(self, entry: Entry) -> None:
        self._title_edit.setText(entry.title)
        self._tags_edit.setText(', '.join(entry.tags))
        self._modified_label.setText(
            entry.modified.astimezone().strftime('%Y-%m-%d %H:%M')
        )
        self._content_edit.setPlainText(entry.content)

    def _set_enabled(self, enabled: bool) -> None:
        self._title_edit.setEnabled(enabled)
        self._tags_edit.setEnabled(enabled)
        self._content_edit.setEnabled(enabled)
        self._apply_btn.setEnabled(enabled)
        self._cancel_btn.setEnabled(enabled)

    @Slot(bool)
    def _on_apply(self, _checked: bool = False) -> None:
        if self._entry is None:
            return
        self._entry.title = self._title_edit.text()
        self._entry.tags = [t.strip() for t in self._tags_edit.text().split(',') if t.strip()]
        self._entry.content = self._content_edit.toPlainText()
        self.entry_changed.emit(self._entry, True)
        self.refresh_modified()

    def _on_cancel(self) -> None:
        if self._entry is None:
            return
        self._load_from_entry(self._entry)
