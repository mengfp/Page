"""
ui/entry_list.py - left panel: search bar, filters + entry table (Title | Date | Tags)

Layout:
    [Search bar                    ]
    [ filter sidebar | gap | table Title | Date | Tags ]

Signals:
    entry_selected(Entry, int) — (entry, previous_row); previous_row -1 if none
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QLineEdit, QMenu, QLabel, QStyle, QStyleOptionFrame, QStyledItemDelegate,
    QStyleOptionViewItem, QAbstractItemView, QHeaderView, QListWidget,
    QListWidgetItem, QFrame,
)
from PySide6.QtCore import Signal, Qt, QPoint
from PySide6.QtGui import QFont, QPalette

from store import Store, Entry

_ALL = "All"

# 只读区统一浅灰（比 #e4e4e4 亮，接近 Win 窗口底，避免发闷）
_READONLY_BG = "#f0f0f0"
_READONLY_BORDER = "#d4d4d4"
_READONLY_HEADER_HOVER = "#e8e8e8"


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
        # 左侧多留空，Search 不要紧贴窗口边
        layout.setContentsMargins(8, 4, 4, 4)
        layout.setSpacing(4)
        self.setStyleSheet(
            f"""
            EntryListPanel {{ background-color: {_READONLY_BG}; }}
            QLineEdit#entryListSearch {{
                background-color: #ffffff;
                border: 1px solid {_READONLY_BORDER};
            }}
            """
        )

        self._search_edit = QLineEdit()
        self._search_edit.setObjectName("entryListSearch")
        self._search_edit.setPlaceholderText("Search...")
        self._search_edit.setToolTip(
            "Filter by title, body and tags. Combine with the tag list on the left."
        )
        self._search_edit.textChanged.connect(self._refresh)
        layout.addWidget(self._search_edit)

        mid_row = QHBoxLayout()
        mid_row.setSpacing(0)
        mid_row.setContentsMargins(0, 0, 0, 0)

        self._entry_table = QTableWidget(0, 3)
        self._entry_table.setHorizontalHeaderLabels(["Title", "Date", "Tags"])
        self._entry_table.setMinimumWidth(360)
        hdr = self._entry_table.horizontalHeader()
        _hdr_h = max(28, hdr.sizeHint().height())

        # 侧栏：与右侧数据表区分开（不同底 + 右边框 + 圆角），避免像同一表格的 4 列
        self._filter_sidebar = QFrame()
        self._filter_sidebar.setObjectName("filterSidebar")
        self._filter_sidebar.setStyleSheet(
            f"""
            QFrame#filterSidebar {{
                background-color: {_READONLY_BG};
                border: 1px solid {_READONLY_BORDER};
                border-right: 2px solid {_READONLY_BORDER};
                border-radius: 8px 0 0 8px;
            }}
            """
        )
        _side_inner_w = 112
        self._filter_sidebar.setFixedWidth(_side_inner_w + 16)
        side_lay = QVBoxLayout(self._filter_sidebar)
        side_lay.setContentsMargins(8, 0, 10, 0)
        side_lay.setSpacing(0)

        _header_bar_ss = """
            QWidget#filtersHeaderBand {
                background-color: transparent;
                border: none;
                border-bottom: 1px solid palette(midlight);
            }
            QLabel#filtersHeaderLabel {
                background-color: transparent;
                color: palette(window-text);
                font-weight: 600;
                font-size: 11px;
                padding: 6px 4px 6px 2px;
            }
        """
        self._filters_header_band = QFrame()
        self._filters_header_band.setObjectName("filtersHeaderBand")
        self._filters_header_band.setFixedHeight(_hdr_h)
        self._filters_header_band.setStyleSheet(_header_bar_ss)
        self._filters_heading = QLabel("Filters")
        self._filters_heading.setObjectName("filtersHeaderLabel")
        self._filters_heading.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        hb_l = QVBoxLayout(self._filters_header_band)
        hb_l.setContentsMargins(0, 0, 0, 0)
        hb_l.addWidget(self._filters_heading)
        side_lay.addWidget(self._filters_header_band)

        self._tag_list = QListWidget()
        self._tag_list.setFixedWidth(_side_inner_w)
        self._tag_list.setFrameShape(QFrame.Shape.NoFrame)
        self._tag_list.currentItemChanged.connect(self._refresh)
        side_lay.addWidget(self._tag_list, 1)
        mid_row.addWidget(self._filter_sidebar)
        mid_row.addSpacing(10)

        hdr.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        hdr.setStyleSheet(
            f"""
            QHeaderView {{
                background-color: {_READONLY_BG};
            }}
            QHeaderView::section {{
                background-color: {_READONLY_BG};
                color: #606060;
                font-weight: normal;
                padding: 4px 6px;
                border: none;
                border-bottom: 1px solid {_READONLY_BORDER};
                border-left: 1px solid {_READONLY_BORDER};
            }}
            QHeaderView::section:first {{
                border-left: none;
            }}
            QHeaderView::section:hover,
            QHeaderView::section:pressed {{
                background-color: {_READONLY_HEADER_HOVER};
                color: #303030;
            }}
            """
        )
        hdr.setFixedHeight(_hdr_h)
        hdr.setHighlightSections(False)
        hdr.setMinimumSectionSize(64)
        # 必须全部 Interactive 才能拖列宽；Stretch 列在 Qt 里不能手工调
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        self._entry_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self._entry_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self._entry_table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self._entry_table.setShowGrid(True)
        self._entry_table.verticalHeader().setVisible(False)
        # 只读列表：整表统一灰底，不再白/灰交替
        self._entry_table.setAlternatingRowColors(False)
        self._entry_table.setStyleSheet(
            f"""
            QTableWidget {{
                background-color: {_READONLY_BG};
                gridline-color: {_READONLY_BORDER};
                border: 1px solid {_READONLY_BORDER};
                border-radius: 0 6px 6px 0;
            }}
            QTableWidget::item {{
                background-color: {_READONLY_BG};
            }}
            QTableWidget::item:selected, QTableWidget::item:selected:active {{
                background-color: #c5ddf5;
                color: palette(text);
            }}
            QTableWidget::item:selected:!active {{
                background-color: #d6e8f9;
                color: palette(text);
            }}
            """
        )
        self._tag_list.setStyleSheet(
            """
            QListWidget {
                background-color: transparent;
                border: none;
                outline: none;
            }
            QListWidget::item {
                padding: 4px 2px;
                border-radius: 4px;
            }
            QListWidget::item:selected {
                background-color: #b8d4f0;
                color: palette(text);
            }
            """
        )
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
        heading_left = self._filters_heading.mapTo(self, QPoint(0, 0)).x()
        delta = target_x - heading_left
        self._filters_heading.setContentsMargins(max(0, delta), 0, 0, 0)
        if delta < 0:
            self._filters_heading.setStyleSheet(
                "margin-left: %dpx; background: transparent; color: palette(placeholder-text);"
                " font-weight: normal; padding: 4px 6px;" % delta
            )
        else:
            self._filters_heading.setStyleSheet(
                "background: transparent; color: palette(placeholder-text);"
                " font-weight: normal; padding: 4px 6px;"
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

    def _apply_entry_table_column_widths(self) -> None:
        """
        按内容算初始列宽；三列均 Interactive，表头分割线可拖。
         viewport 比列宽总和多时，余量分给 Title / Tags，避免右侧空一条。
        """
        hdr = self._entry_table.horizontalHeader()
        fm = self._entry_table.fontMetrics()
        pad = 28  # 表头 padding + 余量

        def text_w(s: str) -> int:
            return fm.horizontalAdvance(s) + pad

        headers = ("Title", "Date", "Tags")
        mins = (120, 140, 72)
        maxs = (560, 200, 420)

        widths = [text_w(headers[c]) for c in range(3)]
        for col in range(3):
            for row in range(self._entry_table.rowCount()):
                it = self._entry_table.item(row, col)
                if it and it.text():
                    widths[col] = max(widths[col], text_w(it.text()))
            widths[col] = max(mins[col], min(maxs[col], widths[col]))

        vp = max(0, self._entry_table.viewport().width() - 4)
        total = sum(widths)
        if vp > total:
            extra = vp - total
            widths[0] += (extra * 2) // 3
            widths[2] += extra - (extra * 2) // 3

        for c in range(3):
            hdr.setSectionResizeMode(c, QHeaderView.ResizeMode.Interactive)
            self._entry_table.setColumnWidth(c, widths[c])

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
            _ro = Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled
            it0 = QTableWidgetItem(title)
            it0.setFlags(_ro)
            it0.setToolTip(tip)
            it1 = QTableWidgetItem(when)
            it1.setFlags(_ro)
            it1.setToolTip(tip)
            it2 = QTableWidgetItem(tags)
            it2.setFlags(_ro)
            it2.setToolTip(tip)
            self._entry_table.setItem(row, 0, it0)
            self._entry_table.setItem(row, 1, it1)
            self._entry_table.setItem(row, 2, it2)
        self._entry_table.blockSignals(False)

        self._apply_entry_table_column_widths()

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
