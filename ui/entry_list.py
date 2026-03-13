"""
ui/entry_list.py - left panel: search bar, tag sidebar, entry list

Layout:
    [Search bar                    ]
    [Tag list      | Entry list    ]
    [New Entry button              ]

Signals:
    entry_selected(Entry)   - emitted when user selects an entry
    new_entry_requested()   - emitted when user clicks New Entry
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QLineEdit, QPushButton,
)
from PySide6.QtCore import Signal, Qt

from store import Store, Entry

_ALL = "All"


class EntryListPanel(QWidget):
    entry_selected = Signal(object)   # Entry
    new_entry_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._store: Store | None = None
        self._displayed: list[Entry] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Search bar
        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("Search...")
        self._search_edit.textChanged.connect(self._refresh)
        layout.addWidget(self._search_edit)

        # Tag sidebar + entry list side by side
        mid_row = QHBoxLayout()
        mid_row.setSpacing(4)

        self._tag_list = QListWidget()
        self._tag_list.setFixedWidth(100)
        self._tag_list.currentItemChanged.connect(self._refresh)
        mid_row.addWidget(self._tag_list)

        self._entry_list = QListWidget()
        self._entry_list.currentItemChanged.connect(self._on_selection_changed)
        mid_row.addWidget(self._entry_list, 1)

        layout.addLayout(mid_row, 1)

        # New entry button
        new_btn = QPushButton("New Entry")
        new_btn.clicked.connect(self.new_entry_requested)
        layout.addWidget(new_btn)

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

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

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

        # Restore previous tag selection
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

        # Filter by keyword
        entries = self._store.search(keyword) if keyword else list(self._store.entries)

        # Filter by tag
        if tag and tag != _ALL:
            entries = [e for e in entries if tag in e.tags]

        # Sort by modified descending
        entries = self._store.sorted_by_modified(entries)

        # Remember current selection
        current = self.current_entry() if preserve_selection else None

        self._displayed = entries
        self._entry_list.blockSignals(True)
        self._entry_list.clear()
        for entry in entries:
            text = entry.title if entry.title else "(untitled)"
            item = QListWidgetItem(text)
            item.setToolTip(entry.modified.astimezone().strftime('%Y-%m-%d %H:%M'))
            self._entry_list.addItem(item)
        self._entry_list.blockSignals(False)

        # Restore selection without triggering entry_selected signal
        if current is not None:
            self.select_entry(current)

    def _on_selection_changed(self, current: QListWidgetItem, previous: QListWidgetItem) -> None:
        entry = self.current_entry()
        if entry is not None:
            self.entry_selected.emit(entry)
