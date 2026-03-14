"""
ui/entry_editor.py - right panel: title, tags (chips + Add), content, New/Apply/Cancel
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit,
    QPlainTextEdit, QLabel, QFrame, QPushButton,
    QScrollArea, QSizePolicy, QMenu, QDialog, QDialogButtonBox,
    QCompleter, QMessageBox,
)
from PySide6.QtCore import Signal, Slot, Qt, QStringListModel
from PySide6.QtGui import QFont, QPalette

from store import Entry

_CHIP_STYLE = """
#tagChip {
    background-color: #c8c8c8;
    color: #111;
    border: 1px solid #888;
    border-radius: 4px;
    padding: 0px 5px;
}
"""

# Tags row: no white panel — match window background
_TAG_ROW_QSS = """
QScrollArea { border: none; background: transparent; }
QScrollArea > QWidget > QWidget { background: transparent; }
"""


class TagChipBar(QWidget):
    """Small chips in a row; right-click chip → Delete; Add → tag dialog."""

    _CHIP_H = 18

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tags: list[str] = []
        self._suggestions: list[str] = []

        # 与表单行高对齐，避免 chip 视觉上偏上、和 "Tags:" 不齐
        self._tag_row_h = 28
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        row.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self.setMinimumHeight(self._tag_row_h)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(False)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setStyleSheet(_TAG_ROW_QSS)
        self._scroll.viewport().setAutoFillBackground(False)
        self._scroll.setFixedHeight(self._tag_row_h)
        self._scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self._chips_inner = QWidget()
        self._chips_inner.setAutoFillBackground(False)
        self._chips_inner.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._chips_inner.setFixedHeight(self._tag_row_h)
        self._chips_layout = QHBoxLayout(self._chips_inner)
        _pad_v = max(0, (self._tag_row_h - self._CHIP_H) // 2)
        self._chips_layout.setContentsMargins(2, _pad_v, 2, _pad_v)
        self._chips_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self._chips_layout.setSpacing(4)
        self._chips_layout.addStretch()
        self._scroll.setWidget(self._chips_inner)
        row.addWidget(self._scroll, 1)

        self._add_tag_btn = QPushButton("Add")
        self._add_tag_btn.setFlat(True)
        self._add_tag_btn.setFixedHeight(self._tag_row_h)
        self._add_tag_btn.setToolTip(
            "Add tags separated by commas. Suggestions as you type."
        )
        self._add_tag_btn.clicked.connect(self._on_new_clicked)
        row.addWidget(self._add_tag_btn)

    def set_available_tags(self, names: list[str]) -> None:
        self._suggestions = sorted(set(names))

    def get_tags(self) -> list[str]:
        return list(self._tags)

    def set_tags(self, tags: list[str]) -> None:
        self.clear()
        for t in tags:
            t = str(t).strip()
            if t and t not in self._tags:
                self._tags.append(t)
                self._add_chip(t)

    def clear(self) -> None:
        while self._chips_layout.count() > 1:
            item = self._chips_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._tags.clear()
        self._resize_chips_inner()

    def has_any_tag_or_input(self) -> bool:
        return bool(self._tags)

    def commit_pending_input(self) -> None:
        pass

    def _resize_chips_inner(self) -> None:
        w = 6
        for i in range(self._chips_layout.count() - 1):
            it = self._chips_layout.itemAt(i)
            if it.widget():
                w += it.widget().sizeHint().width() + 4
        self._chips_inner.setMinimumWidth(max(w, 40))
        self._chips_inner.resize(max(w, 40), self._tag_row_h)

    def _add_chip(self, text: str) -> None:
        chip = QFrame()
        chip.setObjectName("tagChip")
        chip.setFixedHeight(self._CHIP_H)
        chip.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        chip.setStyleSheet(_CHIP_STYLE)
        chip.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        lab = QLabel(text)
        lab.setStyleSheet("color: #111; background: transparent; border: none;")
        f = QFont(lab.font())
        f.setPointSize(max(f.pointSize() - 3, 7))
        lab.setFont(f)
        inner = QHBoxLayout(chip)
        inner.setContentsMargins(4, 0, 4, 0)
        inner.addWidget(lab)

        def _menu(pos):
            m = QMenu(self)
            m.addAction("Delete", lambda: self._remove_chip(text, chip))

            m.exec(chip.mapToGlobal(pos))

        chip.customContextMenuRequested.connect(_menu)
        self._chips_layout.insertWidget(self._chips_layout.count() - 1, chip)
        self._resize_chips_inner()

    def _remove_chip(self, text: str, chip: QFrame) -> None:
        if text in self._tags:
            self._tags.remove(text)
        chip.deleteLater()
        self._resize_chips_inner()

    def _on_new_clicked(self) -> None:
        dlg = QDialog(self)
        dlg.setWindowTitle("Add tags")
        dlg.setMinimumWidth(520)
        dlg.setMinimumHeight(140)
        form = QFormLayout(dlg)
        edit = QLineEdit()
        edit.setPlaceholderText("tag or a, b, c")
        edit.setMinimumWidth(400)
        if self._suggestions:
            c = QCompleter(dlg)
            c.setModel(QStringListModel(self._suggestions))
            c.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            c.setFilterMode(Qt.MatchFlag.MatchContains)
            edit.setCompleter(c)
        form.addRow("Tags:", edit)
        hint = QLabel(
            "Separate several tags with commas. Existing tags are suggested while you type."
        )
        hint.setWordWrap(True)
        hint.setForegroundRole(QPalette.ColorRole.PlaceholderText)
        form.addRow(hint)
        bb = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        form.addRow(bb)
        edit.setFocus()
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        raw = edit.text().strip()
        if not raw:
            return
        for p in raw.replace("，", ",").split(","):
            p = p.strip()
            if p and p not in self._tags:
                self._tags.append(p)
                self._add_chip(p)

    def setEnabled(self, enabled: bool) -> None:
        super().setEnabled(enabled)
        self._add_tag_btn.setEnabled(enabled)


class EntryEditorPanel(QWidget):
    entry_changed = Signal(object, bool)
    pending_entry_discarded = Signal()
    new_draft_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._entry: Entry = Entry()
        self._pending_add: bool = True

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        _ro = "#f0f0f0"
        _bd = "#d4d4d4"
        self.setStyleSheet(
            f"""
            EntryEditorPanel {{ background-color: {_ro}; }}
            QLineEdit#editorTitle, QPlainTextEdit#editorContent {{
                background-color: #ffffff;
                border: 1px solid {_bd};
                color: #202020;
            }}
            QLineEdit#editorDateReadonly,
            QLineEdit#editorDateReadonly:read-only {{
                background-color: {_ro};
                color: #303030;
                border: none;
                padding-left: 0;
            }}
            """
        )

        form = QFormLayout()
        form.setHorizontalSpacing(20)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._title_edit = QLineEdit()
        self._title_edit.setObjectName("editorTitle")
        self._title_edit.setPlaceholderText("Title")
        form.addRow("Title:", self._title_edit)

        self._tag_bar = TagChipBar()
        form.addRow("Tags:", self._tag_bar)

        self._modified_edit = QLineEdit()
        self._modified_edit.setObjectName("editorDateReadonly")
        self._modified_edit.setReadOnly(True)
        self._modified_edit.setPlaceholderText("")
        self._modified_edit.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._modified_edit.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._modified_edit.setFrame(False)
        form.addRow("Date:", self._modified_edit)
        layout.addLayout(form)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(line)

        self._content_edit = QPlainTextEdit()
        self._content_edit.setObjectName("editorContent")
        self._content_edit.setPlaceholderText("Content...")
        layout.addWidget(self._content_edit, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._new_btn = QPushButton("New")
        self._new_btn.setToolTip("Create a blank draft.")
        self._new_btn.clicked.connect(self.new_draft_requested.emit)
        self._apply_btn = QPushButton("Apply")
        self._apply_btn.setToolTip(
            "Save to buffer only. File → Save also flushes to disk."
        )
        self._apply_btn.clicked.connect(self._on_apply)
        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.setToolTip("Revert this form to last Apply.")
        self._cancel_btn.clicked.connect(self._on_cancel)
        btn_row.addWidget(self._new_btn)
        btn_row.addWidget(self._apply_btn)
        btn_row.addWidget(self._cancel_btn)
        layout.addLayout(btn_row)

        self._set_enabled(True)
        self._show_draft_ui()

    def set_available_tags(self, names: list[str]) -> None:
        self._tag_bar.set_available_tags(names)

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
        if self._pending_add:
            return False
        tags = self._tag_bar.get_tags()
        return (
            self._title_edit.text() != self._entry.title
            or tags != self._entry.tags
            or self._content_edit.toPlainText() != self._entry.content
        )

    def is_blank_draft(self) -> bool:
        return self._pending_add and self._form_empty()

    def _app_dirty_draft(self) -> bool:
        return self._pending_add and not self._form_empty()

    def _form_empty(self) -> bool:
        return (
            not self._title_edit.text().strip()
            and not self._tag_bar.has_any_tag_or_input()
            and not self._content_edit.toPlainText().strip()
        )

    def set_entry(self, entry: Entry, *, pending_add: bool) -> None:
        self._entry = entry
        self._pending_add = pending_add
        self._title_edit.setText(entry.title)
        self._tag_bar.set_tags(entry.tags)
        self._content_edit.setPlainText(entry.content)
        if pending_add:
            self._modified_edit.clear()
        else:
            self._modified_edit.setText(
                entry.modified.astimezone().strftime("%Y-%m-%d %H:%M:%S")
            )
        self._set_enabled(True)

    def reset_to_new_draft(self) -> None:
        self.set_entry(Entry(), pending_add=True)

    def refresh_modified(self) -> None:
        if self._entry is not None and not self._pending_add:
            self._modified_edit.setText(
                self._entry.modified.astimezone().strftime("%Y-%m-%d %H:%M:%S")
            )

    def _show_draft_ui(self) -> None:
        self._title_edit.clear()
        self._tag_bar.clear()
        self._modified_edit.clear()
        self._content_edit.clear()

    def _set_enabled(self, enabled: bool) -> None:
        self._title_edit.setEnabled(enabled)
        self._tag_bar.setEnabled(enabled)
        self._content_edit.setEnabled(enabled)
        self._new_btn.setEnabled(enabled)
        self._apply_btn.setEnabled(enabled)
        self._cancel_btn.setEnabled(enabled)

    def apply_to_store(self, *, show_warning: bool = True) -> bool:
        """
        Apply current form into store (buffer only). File → Save also calls this before flush.
        Returns False if title required but empty.
        """
        title = self._title_edit.text()
        tags = self._tag_bar.get_tags()
        content = self._content_edit.toPlainText()
        if self._pending_add:
            if self._form_empty():
                return True
            if not title.strip():
                if show_warning:
                    QMessageBox.warning(
                        self,
                        "Title required",
                        "Enter a title before Apply or Save. The title cannot be empty.",
                    )
                    self._title_edit.setFocus()
                return False
        else:
            if not title.strip():
                if show_warning:
                    QMessageBox.warning(
                        self,
                        "Title required",
                        "Enter a title before Apply or Save. The title cannot be empty.",
                    )
                    self._title_edit.setFocus()
                return False
            if (
                title == self._entry.title
                and tags == self._entry.tags
                and content == self._entry.content
            ):
                return True
        self._entry.title = title
        self._entry.tags = tags
        self._entry.content = content
        self._entry.touch()
        self._pending_add = False
        self.entry_changed.emit(self._entry, True)
        self.refresh_modified()
        return True

    @Slot(bool)
    def _on_apply(self, _checked: bool = False) -> None:
        self.apply_to_store(show_warning=True)

    def _on_cancel(self) -> None:
        if self._pending_add:
            self.pending_entry_discarded.emit()
            self.reset_to_new_draft()
            return
        self._title_edit.setText(self._entry.title)
        self._tag_bar.set_tags(self._entry.tags)
        self._content_edit.setPlainText(self._entry.content)
        self._modified_edit.setText(
            self._entry.modified.astimezone().strftime("%Y-%m-%d %H:%M:%S")
        )
