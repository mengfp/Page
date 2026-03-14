"""
ui/entry_list.py - left panel: search bar, tag sidebar, entry table (Title | Date | Tags)

Layout:
    [Search bar                    ]
    [ Tags (label) | Entry table   ]
    [ tag list     |               ]

Signals:
    entry_selected(Entry, int) — (entry, previous_row); previous_row -1 if none
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QLineEdit, QMenu, QLabel, QStyle, QStyleOptionFrame, QStyledItemDelegate,
    QStyleOptionViewItem, QAbstractItemView, QHeaderView, QListWidget,
    QListWidgetItem,
)
from PySide6.QtCore import Signal, Qt, QPoint
from PySide6.QtGui import QFont, QPalette

from store import Store, Entry

_ALL = "All"


class _ElideDelegate(QStyledItemDelegate):
    """Draw cell text with trailing ellipsis when space is tight."""

    def paint(self, painter, option, index):
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        opt.text = ""
        style = option.widget.style()
        style.drawControl(QStyle.CE_ItemViewItem, opt, painter, option.widget)
        text = index.data(Qt.ItemDataRole.DisplayRole)
        if not text:
            return
        text = str(text)
        painter.save()
        painter.setPen(opt.palette.color(opt.palette.ColorRole.Text))
        painter.setFont(opt.font)
        rect = opt.rect.adjusted(4, 0, -4, 0)
        elided = opt.fontMetrics.elidedText(
            text, Qt.TextElideMode.ElideRight, max(4, rect.width())
        )
        painter.drawText(
            rect,
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            elided,
        )
        painter.restore()


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
        self._search_edit.setToolTip(
            "Filter by title, body and tags. Combine with the tag list on the left."
        )
        self._search_edit.textChanged.connect(self._refresh)
        layout.addWidget(self._search_edit)

        mid_row = QHBoxLayout()
        mid_row.setSpacing(4)

        tag_col = QVBoxLayout()
        tag_col.setSpacing(2)
        tag_col.setContentsMargins(0, 0, 0, 0)
        self._tags_heading = QLabel("Tags")
        self._tags_heading.setFixedWidth(100)
        self._tags_heading.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        self._tags_heading.setForegroundRole(QPalette.ColorRole.PlaceholderText)
        self._tags_heading.setMargin(0)
        tag_col.addWidget(self._tags_heading)
        self._tag_list = QListWidget()
        self._tag_list.setFixedWidth(100)
        self._tag_list.currentItemChanged.connect(self._refresh)
        tag_col.addWidget(self._tag_list)
        mid_row.addLayout(tag_col)

        self._entry_table = QTableWidget(0, 3)
        self._entry_table.setHorizontalHeaderLabels(["Title", "Date", "Tags"])
        # Lighter header; always normal weight (avoid bold on click/focus)
        self._entry_table.horizontalHeader().setStyleSheet(
            """
            QHeaderView::section {
                background-color: palette(base);
                color: palette(placeholder-text);
                font-weight: normal;
                padding: 4px 6px;
                border: none;
                border-bottom: 1px solid palette(midlight);
            }
            QHeaderView::section:hover,
            QHeaderView::section:pressed {
                background-color: palette(alternate-base);
                color: palette(placeholder-text);
                font-weight: normal;
            }
            """
        )
        self._entry_table.horizontalHeader().setHighlightSections(False)
        self._entry_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self._entry_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents
        )
        self._entry_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch
        )
        self._entry_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self._entry_table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self._entry_table.setShowGrid(True)
        self._entry_table.verticalHeader().setVisible(False)
        self._entry_table.setAlternatingRowColors(True)
        delegate = _ElideDelegate(self._entry_table)
        self._entry_table.setItemDelegate(delegate)
        self._entry_table.currentCellChanged.connect(self._on_cell_changed)
        self._entry_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._entry_table.customContextMenuRequested.connect(self._on_entry_table_menu)
        mid_row.addWidget(self._entry_table, 1)

        layout.addLayout(mid_row, 1)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._sync_tags_heading_align()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._sync_tags_heading_align()

    def _sync_tags_heading_align(self) -> None:
        if not self._search_edit.isVisible():
            return
        opt = QStyleOptionFrame()
        self._search_edit.initStyleOption(opt)
        cr = self._search_edit.style().subElementRect(
            QStyle.SubElement.SE_LineEditContents, opt, self._search_edit
        )
        target_x = self._search_edit.mapTo(self, cr.topLeft()).x()
        heading_left = self._tags_heading.mapTo(self, QPoint(0, 0)).x()
        delta = target_x - heading_left
        self._tags_heading.setContentsMargins(max(0, delta), 0, 0, 0)
        self._tags_heading.setStyleSheet(
            f"margin-left: {delta}px;" if delta < 0 else ""
        )

    def set_store(self, store: Store) -> None:
        self._store = store
        self._search_edit.clear()
        self._refresh_tags()
        self._refresh()

    def refresh(self) -> None:
        self._refresh_tags()
        self._refresh_entries(preserve_selection=True)

    def select_entry(self, entry: Entry) -> None:
        for i, e in enumerate(self._displayed):
            if e is entry:
                self._entry_table.blockSignals(True)
                self._entry_table.selectRow(i)
                self._entry_table.blockSignals(False)
                return

    def current_entry(self) -> Entry | None:
        row = self._entry_table.currentRow()
        if 0 <= row < len(self._displayed):
            return self._displayed[row]
        return None

    def clear_selection(self) -> None:
        self._entry_table.blockSignals(True)
        self._entry_table.clearSelection()
        self._entry_table.setCurrentCell(-1, 0)
        self._entry_table.blockSignals(False)

    def set_current_row_silent(self, row: int) -> None:
        self._entry_table.blockSignals(True)
        if row < 0:
            self._entry_table.clearSelection()
            self._entry_table.setCurrentCell(-1, 0)
        else:
            self._entry_table.selectRow(row)
        self._entry_table.blockSignals(False)

    def _on_entry_table_menu(self, pos) -> None:
        idx = self._entry_table.indexAt(pos)
        row = idx.row()
        if row < 0 or row >= len(self._displayed):
            return
        entry = self._displayed[row]
        menu = QMenu(self)
        act = menu.addAction("Delete")
        act.triggered.connect(lambda: self.delete_note_requested.emit(entry))
        menu.exec(self._entry_table.viewport().mapToGlobal(pos))

    def _current_tag(self) -> str:
        item = self._tag_list.currentItem()
        return item.text() if item else _ALL

    def _refresh_tags(self) -> None:
        if self._store is None:
            return
        current_tag = self._current_tag()
        self._tag_list.blockSignals(True)
        self._tag_list.clear()
        all_item = QListWidgetItem(_ALL)
        f = QFont(self._tag_list.font())
        f.setItalic(True)
        all_item.setFont(f)
        all_item.setToolTip("Show all notes (not a tag name)")
        self._tag_list.addItem(all_item)
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

    def _entry_tags_text(self, entry: Entry) -> str:
        return ", ".join(entry.tags) if entry.tags else ""

    def _row_tooltip(self, entry: Entry) -> str:
        title = entry.title or "(untitled)"
        when = entry.modified.astimezone().strftime("%Y-%m-%d %H:%M:%S")
        tags = self._entry_tags_text(entry) or "—"
        return f"{title}\n{when}\n{tags}"

    def _refresh_entries(self, preserve_selection: bool) -> None:
        if self._store is None:
            self._entry_table.setRowCount(0)
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
        self._entry_table.blockSignals(True)
        self._entry_table.setRowCount(len(entries))
        for row, entry in enumerate(entries):
            title = entry.title if entry.title else "(untitled)"
            when = entry.modified.astimezone().strftime("%Y-%m-%d %H:%M")
            tags = self._entry_tags_text(entry)
            tip = self._row_tooltip(entry)
            it0 = QTableWidgetItem(title)
            it0.setToolTip(tip)
            it1 = QTableWidgetItem(when)
            it1.setToolTip(tip)
            it2 = QTableWidgetItem(tags)
            it2.setToolTip(tip)
            self._entry_table.setItem(row, 0, it0)
            self._entry_table.setItem(row, 1, it1)
            self._entry_table.setItem(row, 2, it2)
        self._entry_table.blockSignals(False)

        if current is not None:
            self.select_entry(current)

    def _on_cell_changed(
        self, cur_row: int, _cur_col: int, prev_row: int, _prev_col: int
    ) -> None:
        if cur_row < 0 or cur_row >= len(self._displayed):
            return
        entry = self._displayed[cur_row]
        if cur_row == prev_row and prev_row >= 0:
            return
        self.entry_selected.emit(entry, prev_row if prev_row >= 0 else -1)
