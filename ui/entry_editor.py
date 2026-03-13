"""
ui/entry_editor.py - right panel: title, tags, content editor with Apply/Cancel

Apply  : writes edited fields into the Entry object, emits entry_changed(entry, True)
Cancel : pending draft -> reset to empty draft; saved entry -> reload from entry
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit,
    QPlainTextEdit, QLabel, QFrame, QPushButton,
)
from PySide6.QtCore import Signal, Slot

from store import Entry


class EntryEditorPanel(QWidget):
    entry_changed = Signal(object, bool)  # (Entry, refresh_list)
    pending_entry_discarded = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._entry: Entry = Entry()
        self._pending_add: bool = True

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        form = QFormLayout()

        self._title_edit = QLineEdit()
        self._title_edit.setPlaceholderText("Title")
        form.addRow("Title:", self._title_edit)

        self._tags_edit = QLineEdit()
        self._tags_edit.setPlaceholderText("tag1, tag2, tag3")
        form.addRow("Tags:", self._tags_edit)

        self._modified_label = QLabel()
        form.addRow("Modified:", self._modified_label)

        layout.addLayout(form)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(line)

        self._content_edit = QPlainTextEdit()
        self._content_edit.setPlaceholderText("Content...")
        layout.addWidget(self._content_edit, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._apply_btn = QPushButton("Apply")
        self._apply_btn.clicked.connect(self._on_apply)
        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.clicked.connect(self._on_cancel)
        btn_row.addWidget(self._apply_btn)
        btn_row.addWidget(self._cancel_btn)
        layout.addLayout(btn_row)

        self._set_enabled(True)
        self._show_draft_ui()

    @property
    def pending_add(self) -> bool:
        return self._pending_add

    def uncommitted_input(self) -> bool:
        if self._app_dirty_draft():
            return True
        if self.editor_differs_from_loaded_entry():
            return True
        return False

    def editor_differs_from_loaded_entry(self) -> bool:
        """已入库条目在右侧改过但未 Apply 时 True。"""
        if self._pending_add:
            return False
        tags = [t.strip() for t in self._tags_edit.text().split(",") if t.strip()]
        return (
            self._title_edit.text() != self._entry.title
            or tags != self._entry.tags
            or self._content_edit.toPlainText() != self._entry.content
        )

    def is_blank_draft(self) -> bool:
        """空白草稿：未入库且表单全空（New Entry 再点一次不必重置）。"""
        return self._pending_add and self._form_empty()

    def _app_dirty_draft(self) -> bool:
        """Draft with any content — worth confirming before discard."""
        return self._pending_add and not self._form_empty()

    def _form_empty(self) -> bool:
        return (
            not self._title_edit.text().strip()
            and not self._tags_edit.text().strip()
            and not self._content_edit.toPlainText().strip()
        )

    def set_entry(self, entry: Entry, *, pending_add: bool) -> None:
        """Load entry. pending_add=True: not in store yet, Modified stays blank."""
        self._entry = entry
        self._pending_add = pending_add
        self._title_edit.setText(entry.title)
        self._tags_edit.setText(", ".join(entry.tags))
        self._content_edit.setPlainText(entry.content)
        if pending_add:
            self._modified_label.clear()
        else:
            self._modified_label.setText(
                entry.modified.astimezone().strftime("%Y-%m-%d %H:%M")
            )
        self._set_enabled(True)

    def reset_to_new_draft(self) -> None:
        """Same state as Entry → New Entry (empty title, Modified blank)."""
        self.set_entry(Entry(), pending_add=True)

    def refresh_modified(self) -> None:
        if self._entry is not None and not self._pending_add:
            self._modified_label.setText(
                self._entry.modified.astimezone().strftime("%Y-%m-%d %H:%M")
            )

    def _show_draft_ui(self) -> None:
        self._title_edit.clear()
        self._tags_edit.clear()
        self._modified_label.clear()
        self._content_edit.clear()

    def _set_enabled(self, enabled: bool) -> None:
        self._title_edit.setEnabled(enabled)
        self._tags_edit.setEnabled(enabled)
        self._content_edit.setEnabled(enabled)
        self._apply_btn.setEnabled(enabled)
        self._cancel_btn.setEnabled(enabled)

    @Slot(bool)
    def _on_apply(self, _checked: bool = False) -> None:
        self._entry.title = self._title_edit.text()
        self._entry.tags = [
            t.strip() for t in self._tags_edit.text().split(",") if t.strip()
        ]
        self._entry.content = self._content_edit.toPlainText()
        self._entry.touch()
        self._pending_add = False
        self.entry_changed.emit(self._entry, True)
        self.refresh_modified()

    def _on_cancel(self) -> None:
        if self._pending_add:
            self.pending_entry_discarded.emit()
            self.reset_to_new_draft()
            return
        self._title_edit.setText(self._entry.title)
        self._tags_edit.setText(", ".join(self._entry.tags))
        self._content_edit.setPlainText(self._entry.content)
        self._modified_label.setText(
            self._entry.modified.astimezone().strftime("%Y-%m-%d %H:%M")
        )
