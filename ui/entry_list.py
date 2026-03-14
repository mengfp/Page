"""
ui/entry_list.py - left panel: search bar, tag sidebar, entry list

Layout:
    [Search bar                    ]
    [Tag list      | Entry list    ]

Signals:
    entry_selected(Entry, int) — (entry, previous_row); previous_row -1 if none
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QLineEdit, QMenu,
)
from PySide6.QtCore import Signal, Qt

from store import Store, Entry

_ALL = "All"


class EntryListPanel(QWidget):
    entry_selected = Signal(object, int)  # Entry, previous_row (-1 = no selection)
    delete_note_requested = Signal(object)  # Entry

    def __init__(self, parent=None):
        super().__init__(parent)
        self._store: Store | None = None
        self._displayed: list[Entry] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("Search...")
        self._search_edit.textChanged.connect(self._refresh)
        layout.addWidget(self._search_edit)

        mid_row = QHBoxLayout()
        mid_row.setSpacing(4)

        self._tag_list = QListWidget()
        self._tag_list.setFixedWidth(100)
        self._tag_list.currentItemChanged.connect(self._refresh)
        mid_row.addWidget(self._tag_list)

        self._entry_list = QListWidget()
        self._entry_list.currentItemChanged.connect(self._on_selection_changed)
        self._entry_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._entry_list.customContextMenuRequested.connect(self._on_entry_list_menu)
        mid_row.addWidget(self._entry_list, 1)

        layout.addLayout(mid_row, 1)

    def set_store(self, store: Store) -> None:
        """Load a new store and refresh the display."""
        self._store = store
        self._search_edit.clear()
        self._refresh_tags()
        self._refresh()

    def refresh(self) -> None:
        """Call after store contents change (e.g. entry added/removed)."""
        self._refresh_tags()
        self._refresh_entries(preserve_selection=True)

    def select_entry(self, entry: Entry) -> None:
        """Programmatically select an entry in the list."""
        for i, e in enumerate(self._displayed):
            if e is entry:
                self._entry_list.blockSignals(True)
                self._entry_list.setCurrentRow(i)
                self._entry_list.blockSignals(False)
                return

    def current_entry(self) -> Entry | None:
        row = self._entry_list.currentRow()
        if 0 <= row < len(self._displayed):
            return self._displayed[row]
        return None

    def clear_selection(self) -> None:
        """Clear list selection (e.g. when starting a draft new entry)."""
        self._entry_list.blockSignals(True)
        self._entry_list.clearSelection()
        self._entry_list.setCurrentRow(-1)
        self._entry_list.blockSignals(False)

    def set_current_row_silent(self, row: int) -> None:
        """Restore list selection without emitting entry_selected."""
        self._entry_list.blockSignals(True)
        if row < 0:
            self._entry_list.clearSelection()
            self._entry_list.setCurrentRow(-1)
        else:
            self._entry_list.setCurrentRow(row)
        self._entry_list.blockSignals(False)

    def _on_entry_list_menu(self, pos) -> None:
        row = self._entry_list.row(self._entry_list.itemAt(pos))
        if row < 0 or row >= len(self._displayed):
            return
        entry = self._displayed[row]
        menu = QMenu(self)
        act = menu.addAction("Delete")
        act.triggered.connect(lambda: self.delete_note_requested.emit(entry))
        menu.exec(self._entry_list.mapToGlobal(pos))

    def _current_tag(self) -> str:
        item = self._tag_list.currentItem()
        return item.text() if item else _ALL

    def _refresh_tags(self) -> None:
        if self._store is None:
            return
        current_tag = self._current_tag()

        self._tag_list.blockSignals(True)
        self._tag_list.clear()
        self._tag_list.addItem(_ALL)
        for tag in self._store.all_tags():
            self._tag_list.addItem(tag)

        items = self._tag_list.findItems(current_tag, Qt.MatchFlag.MatchExactly)
        if items:
            self._tag_list.setCurrentItem(items[0])
        else:
            self._tag_list.setCurrentRow(0)
        self._tag_list.blockSignals(False)

    def _refresh(self) -> None:
        self._refresh_entries(preserve_selection=False)

    def _refresh_entries(self, preserve_selection: bool) -> None:
        if self._store is None:
            self._entry_list.clear()
            self._displayed = []
            return

        keyword = self._search_edit.text().strip()
        tag = self._current_tag()

        entries = self._store.search(keyword) if keyword else list(self._store.entries)

        if tag and tag != _ALL:
            entries = [e for e in entries if tag in e.tags]

        entries = self._store.sorted_by_modified(entries)

        current = self.current_entry() if preserve_selection else None

        self._displayed = entries
        self._entry_list.blockSignals(True)
        self._entry_list.clear()
        for entry in entries:
            text = entry.title if entry.title else "(untitled)"
            item = QListWidgetItem(text)
            item.setToolTip(entry.modified.astimezone().strftime('%Y-%m-%d %H:%M:%S'))
            self._entry_list.addItem(item)
        self._entry_list.blockSignals(False)

        if current is not None:
            self.select_entry(current)

    def _on_selection_changed(self, current: QListWidgetItem, previous: QListWidgetItem) -> None:
        entry = self.current_entry()
        if entry is None:
            return
        prev_row = self._entry_list.row(previous) if previous is not None else -1
        self.entry_selected.emit(entry, prev_row)
