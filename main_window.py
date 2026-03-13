"""
main_window.py - main application window

Layout:
    [Menu Bar]
    [Left: EntryListPanel | Right: EntryEditorPanel]
    [Status Bar]
"""

import os
import traceback

from PySide6.QtWidgets import (
    QMainWindow, QSplitter, QFileDialog,
    QMessageBox, QStatusBar,
)
from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QAction, QKeySequence, QCloseEvent

from app import App
from store import Entry
from ui.entry_list import EntryListPanel
from ui.entry_editor import EntryEditorPanel
from ui.dialogs import PassphraseDialog, NewPassphraseDialog

FILE_FILTER = "Page Files (*.page);;All Files (*)"


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self._app = App()
        self.setWindowTitle("Page")
        self.resize(900, 600)

        self._build_menu()
        self._build_ui()
        self._build_status_bar()
        # Same Store as App — list panel must not stay _store=None until File>New
        self._list_panel.set_store(self._app.store)
        self._update_title()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_menu(self):
        mb = self.menuBar()

        # File menu
        file_menu = mb.addMenu("File")

        act_new = QAction("New", self)
        act_new.setShortcut(QKeySequence.StandardKey.New)
        act_new.triggered.connect(self._on_new)
        file_menu.addAction(act_new)

        act_open = QAction("Open...", self)
        act_open.setShortcut(QKeySequence.StandardKey.Open)
        act_open.triggered.connect(self._on_open)
        file_menu.addAction(act_open)

        file_menu.addSeparator()

        act_save = QAction("Save", self)
        act_save.setShortcut(QKeySequence.StandardKey.Save)
        act_save.triggered.connect(self._on_save)
        file_menu.addAction(act_save)

        act_save_as = QAction("Save As...", self)
        act_save_as.setShortcut(QKeySequence.StandardKey.SaveAs)
        act_save_as.triggered.connect(self._on_save_as)
        file_menu.addAction(act_save_as)

        file_menu.addSeparator()

        act_quit = QAction("Quit", self)
        act_quit.setShortcut(QKeySequence.StandardKey.Quit)
        act_quit.triggered.connect(self.close)
        file_menu.addAction(act_quit)

        # Entry menu
        entry_menu = mb.addMenu("Entry")

        act_new_entry = QAction("New Entry", self)
        act_new_entry.triggered.connect(self._on_new_entry)
        entry_menu.addAction(act_new_entry)

        act_delete_entry = QAction("Delete Entry", self)
        act_delete_entry.setShortcut(QKeySequence.StandardKey.Delete)
        act_delete_entry.triggered.connect(self._on_delete_entry)
        entry_menu.addAction(act_delete_entry)

    def _build_ui(self):
        splitter = QSplitter(Qt.Orientation.Horizontal)

        self._list_panel = EntryListPanel()
        self._list_panel.setMinimumWidth(200)
        self._list_panel.entry_selected.connect(self._on_entry_selected)
        self._list_panel.new_entry_requested.connect(self._on_new_entry)
        splitter.addWidget(self._list_panel)

        self._editor_panel = EntryEditorPanel()
        splitter.addWidget(self._editor_panel)
        self._editor_panel.entry_changed.connect(self._on_entry_changed)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)

        self.setCentralWidget(splitter)

    def _build_status_bar(self):
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)

    # ------------------------------------------------------------------
    # File operations
    # ------------------------------------------------------------------

    def _on_new(self):
        try:
            if not self._confirm_discard():
                return
            self._app.new()
            self._list_panel.set_store(self._app.store)
            self._editor_panel.set_entry(None)
            self._update_title()
            self._status("New file created.")
        except Exception as e:
            traceback.print_exception(type(e), e, e.__traceback__)
            QMessageBox.critical(self, "Error", f"Operation failed:\n{e}")

    def _on_open(self):
        if not self._confirm_discard():
            return

        path, _ = QFileDialog.getOpenFileName(self, "Open File", "", FILE_FILTER)
        if not path:
            return

        dlg = PassphraseDialog(self, filename=os.path.basename(path))
        if dlg.exec() != PassphraseDialog.DialogCode.Accepted:
            return

        passphrase = dlg.passphrase()
        try:
            self._app.open(path, passphrase)
        except Exception as e:
            traceback.print_exception(type(e), e, e.__traceback__)
            QMessageBox.critical(self, "Error", f"Failed to open file:\n{e}")
            return

        self._list_panel.set_store(self._app.store)
        self._editor_panel.set_entry(None)
        self._update_title()
        self._status(f"Opened: {path}")

    def _on_save(self):
        if self._app.path is None:
            # New file: ask for path and passphrase
            self._save_new_file()
        else:
            self._do_save()

    def _on_save_as(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save As", "", FILE_FILTER)
        if not path:
            return
        if not path.endswith('.page'):
            path += '.page'

        dlg = NewPassphraseDialog(self)
        if dlg.exec() != NewPassphraseDialog.DialogCode.Accepted:
            return

        try:
            self._app.save_as(path, dlg.passphrase())
        except Exception as e:
            traceback.print_exception(type(e), e, e.__traceback__)
            QMessageBox.critical(self, "Error", f"Failed to save file:\n{e}")
            return

        self._editor_panel.refresh_modified()
        self._update_title()
        self._status(f"Saved as: {path}")

    def _save_new_file(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save File", "", FILE_FILTER)
        if not path:
            return
        if not path.endswith('.page'):
            path += '.page'

        dlg = NewPassphraseDialog(self)
        if dlg.exec() != NewPassphraseDialog.DialogCode.Accepted:
            return

        try:
            self._app.save_as(path, dlg.passphrase())
        except Exception as e:
            traceback.print_exception(type(e), e, e.__traceback__)
            QMessageBox.critical(self, "Error", f"Failed to save file:\n{e}")
            return

        self._editor_panel.refresh_modified()
        self._update_title()
        self._status(f"Saved: {path}")

    def _do_save(self):
        try:
            self._app.save()
        except Exception as e:
            traceback.print_exception(type(e), e, e.__traceback__)
            QMessageBox.critical(self, "Error", f"Failed to save:\n{e}")
            return
        self._editor_panel.refresh_modified()
        self._update_title()
        self._status("Saved.")

    # ------------------------------------------------------------------
    # Entry operations
    # ------------------------------------------------------------------

    def _on_new_entry(self):
        try:
            entry = Entry(title="New Entry")
            self._app.add_entry(entry)
            self._list_panel.refresh()
            self._list_panel.select_entry(entry)
            self._editor_panel.set_entry(entry)
            self._update_title()
        except Exception as e:
            traceback.print_exception(type(e), e, e.__traceback__)
            QMessageBox.critical(self, "Error", f"Operation failed:\n{e}")

    def _on_delete_entry(self):
        try:
            entry = self._list_panel.current_entry()
            if entry is None:
                return
            reply = QMessageBox.question(
                self, "Delete Entry",
                f"Delete '{entry.title}'?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
            self._app.remove_entry(entry)
            self._list_panel.refresh()
            self._editor_panel.set_entry(None)
            self._update_title()
        except Exception as e:
            traceback.print_exception(type(e), e, e.__traceback__)
            QMessageBox.critical(self, "Error", f"Operation failed:\n{e}")

    def _on_entry_selected(self, entry: Entry):
        try:
            self._editor_panel.set_entry(entry)
        except Exception as e:
            traceback.print_exception(type(e), e, e.__traceback__)
            QMessageBox.critical(self, "Error", f"Operation failed:\n{e}")

    @Slot(object, bool)
    def _on_entry_changed(self, entry, refresh_list):
        """Must match EntryEditorPanel.entry_changed Signal(object, bool) — no default args on refresh_list or PySide may not register the slot correctly."""
        try:
            self._app.update_entry(entry)
            if refresh_list:
                self._list_panel.refresh()
            self._update_title()
        except Exception as e:
            traceback.print_exception(type(e), e, e.__traceback__)
            QMessageBox.critical(self, "Error", f"Operation failed:\n{e}")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _confirm_discard(self) -> bool:
        """Return True if it is safe to discard current state."""
        if not self._app.dirty:
            return True
        reply = QMessageBox.question(
            self, "Unsaved Changes",
            "You have unsaved changes. Discard them?",
            QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
        )
        return reply == QMessageBox.StandardButton.Discard

    def _update_title(self):
        name = os.path.basename(self._app.path) if self._app.path else "Untitled"
        dirty = " *" if self._app.dirty else ""
        self.setWindowTitle(f"Page - {name}{dirty}")

    def _status(self, msg: str):
        self._status_bar.showMessage(msg, 5000)

    def closeEvent(self, event: QCloseEvent):
        if self._confirm_discard():
            event.accept()
        else:
            event.ignore()
