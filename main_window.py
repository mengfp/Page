"""
main_window.py - main application window

Layout:
    [Menu Bar]
    [Left: EntryListPanel (table) | Right: EntryEditorPanel]
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
from version import APP_NAME, __version__
from ui.entry_list import EntryListPanel
from ui.entry_editor import EntryEditorPanel
from ui.dialogs import PassphraseDialog, NewPassphraseDialog

FILE_FILTER = "Page Files (*.page);;All Files (*)"


def _question_msg(
    parent,
    title: str,
    text: str,
    *,
    informative: str = "",
    primary: str = "Discard",
    secondary: str = "Cancel",
) -> bool:
    """
    Discard + Cancel (or Delete + Cancel). Returns True if primary was clicked.
    No Yes/No — buttons are self-explanatory. Default button: Cancel.
    """
    m = QMessageBox(parent)
    m.setWindowTitle(title)
    m.setText(text)
    m.setIcon(QMessageBox.Icon.Question)
    m.setInformativeText(
        informative
        or "Changes apply to the open file in memory until you use File → Save."
    )
    role = (
        QMessageBox.ButtonRole.DestructiveRole
        if primary in ("Discard", "Delete")
        else QMessageBox.ButtonRole.AcceptRole
    )
    b_ok = m.addButton(primary, role)
    b_cancel = m.addButton(secondary, QMessageBox.ButtonRole.RejectRole)
    m.setDefaultButton(b_cancel)
    m.exec()
    return m.clickedButton() is b_ok


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
        self._list_panel.clear_selection()
        self._editor_panel.reset_to_new_draft()
        self._sync_tag_suggestions()
        self._update_title()

    def _sync_tag_suggestions(self) -> None:
        self._editor_panel.set_available_tags(self._app.store.all_tags())

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

        # Delete: list context menu + shortcut (not in File menu)
        act_delete = QAction("Delete", self)
        act_delete.setShortcut(QKeySequence.StandardKey.Delete)
        act_delete.triggered.connect(self._on_delete_entry)
        self.addAction(act_delete)

        help_menu = mb.addMenu("Help")
        act_about = QAction("About Page", self)
        act_about.setMenuRole(QAction.MenuRole.AboutRole)
        act_about.triggered.connect(self._on_about)
        help_menu.addAction(act_about)

    @Slot()
    def _on_about(self) -> None:
        QMessageBox.about(
            self,
            f"About {APP_NAME}",
            f"{APP_NAME}\n\nVersion {__version__}\n\n"
            "Local encrypted notes. Data stays on this machine.",
        )

    def _build_ui(self):
        splitter = QSplitter(Qt.Orientation.Horizontal)

        self._list_panel = EntryListPanel()
        self._list_panel.setMinimumWidth(280)
        self._list_panel.entry_selected.connect(self._on_entry_selected)
        self._list_panel.delete_note_requested.connect(self._on_delete_note)
        splitter.addWidget(self._list_panel)

        self._editor_panel = EntryEditorPanel()
        splitter.addWidget(self._editor_panel)
        self._editor_panel.entry_changed.connect(self._on_entry_changed)
        self._editor_panel.pending_entry_discarded.connect(self._on_pending_entry_discarded)
        self._editor_panel.new_draft_requested.connect(self._on_new_draft)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)

        self.setCentralWidget(splitter)

    def _build_status_bar(self):
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)

    # ------------------------------------------------------------------
    # File operations
    # ------------------------------------------------------------------

    def _report_error(self, exc: BaseException, message: str = "Operation failed") -> None:
        traceback.print_exception(type(exc), exc, exc.__traceback__)
        QMessageBox.critical(self, "Error", f"{message}\n\n{exc}")

    def _on_new(self):
        try:
            r = self._offer_save_or_discard("Start a new file without saving?")
            if r == "cancel":
                return
            if r == "save" and not self._flush_document():
                return
            self._app.new()
            self._list_panel.set_store(self._app.store)
            self._list_panel.clear_selection()
            self._editor_panel.reset_to_new_draft()
            self._sync_tag_suggestions()
            self._update_title()
            self._status("New file created.")
        except Exception as e:
            self._report_error(e)

    def _on_open(self):
        r = self._offer_save_or_discard("Open another file without saving?")
        if r == "cancel":
            return
        if r == "save" and not self._flush_document():
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
            self._report_error(e, "Failed to open file")
            return

        self._list_panel.set_store(self._app.store)
        self._list_panel.clear_selection()
        self._editor_panel.reset_to_new_draft()
        self._sync_tag_suggestions()
        self._update_title()
        self._status(f"Opened: {path}")

    def _on_save(self):
        """File → Save = apply (buffer) + flush to disk."""
        if not self._editor_panel.apply_to_store():
            return
        if self._app.path is None:
            self._save_new_file()
        else:
            self._do_save()

    def _on_save_as(self):
        if not self._editor_panel.apply_to_store():
            return
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

    def _save_new_file(self) -> bool:
        path, _ = QFileDialog.getSaveFileName(self, "Save File", "", FILE_FILTER)
        if not path:
            return False
        if not path.endswith('.page'):
            path += '.page'

        dlg = NewPassphraseDialog(self)
        if dlg.exec() != NewPassphraseDialog.DialogCode.Accepted:
            return False

        try:
            self._app.save_as(path, dlg.passphrase())
        except Exception as e:
            self._report_error(e, "Failed to save file")
            return False

        self._editor_panel.refresh_modified()
        self._update_title()
        self._status(f"Saved: {path}")
        return True

    def _do_save(self) -> bool:
        try:
            self._app.save()
        except Exception as e:
            self._report_error(e, "Failed to save")
            return False
        self._editor_panel.refresh_modified()
        self._update_title()
        self._status("Saved.")
        return True

    def _flush_document(self) -> bool:
        """Apply + write disk (same as File → Save)."""
        if not self._editor_panel.apply_to_store():
            return False
        if self._app.path is None:
            return self._save_new_file()
        return self._do_save()

    # ------------------------------------------------------------------
    # Entry operations
    # ------------------------------------------------------------------

    def _on_new_draft(self):
        try:
            if self._editor_panel.is_blank_draft():
                return
            if self._editor_panel.uncommitted_input():
                msg = (
                    "Unapplied edits to this entry will be lost. Start a new draft?"
                    if self._editor_panel.editor_differs_from_loaded_entry()
                    and not self._editor_panel.pending_add
                    else "Discard current draft and start a new blank draft?"
                )
                if not _question_msg(
                    self,
                    "New draft?",
                    msg,
                    informative=(
                        "Cancel keeps the current editor. Discard clears the list selection "
                        "and opens a blank draft. Nothing is written to disk until File → Save."
                    ),
                ):
                    return
            self._list_panel.clear_selection()
            self._editor_panel.reset_to_new_draft()
        except Exception as e:
            self._report_error(e)

    def _on_pending_entry_discarded(self):
        self._update_title()

    def _on_delete_entry(self):
        entry = self._list_panel.current_entry()
        if entry is not None:
            self._on_delete_note(entry)

    def _on_delete_note(self, entry: Entry):
        try:
            if not _question_msg(
                self,
                "Delete",
                f"Remove '{entry.title or '(untitled)'}' from the list?",
                primary="Delete",
                informative=(
                    "The note is removed from the list in memory. "
                    "To remove it from the file on disk, choose File → Save afterwards."
                ),
            ):
                return
            self._app.remove_entry(entry)
            self._list_panel.refresh()
            self._list_panel.clear_selection()
            self._editor_panel.reset_to_new_draft()
            self._sync_tag_suggestions()
            self._update_title()
        except Exception as e:
            self._report_error(e)

    @Slot(object, int)
    def _on_entry_selected(self, entry: Entry, previous_row: int):
        try:
            if self._editor_panel.uncommitted_input():
                if not _question_msg(
                    self,
                    "Discard?",
                    "You have a draft or unapplied edits. Switch entry and lose them?",
                    informative=(
                        "Cancel keeps the previous list selection. Discard opens the "
                        "other note and drops edits not yet applied on the current one."
                    ),
                ):
                    self._list_panel.set_current_row_silent(previous_row)
                    return
            self._editor_panel.set_entry(entry, pending_add=False)
            self._sync_tag_suggestions()
        except Exception as e:
            self._report_error(e)

    @Slot(object, bool)
    def _on_entry_changed(self, entry, refresh_list):
        """Must match EntryEditorPanel.entry_changed Signal(object, bool) — no default args on refresh_list or PySide may not register the slot correctly."""
        try:
            is_new = entry not in self._app.store.entries
            if is_new:
                self._app.add_entry(entry)
            else:
                self._app.update_entry(entry)
            if refresh_list:
                self._list_panel.refresh()
                if is_new:
                    # Was draft → now in list; new Apply must be a new Entry, not update same row
                    self._list_panel.clear_selection()
                    self._editor_panel.reset_to_new_draft()
                else:
                    self._list_panel.select_entry(entry)
            self._sync_tag_suggestions()
            self._update_title()
        except Exception as e:
            self._report_error(e)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _offer_save_or_discard(self, detail: str) -> str:
        """ok | save | discard | cancel — Save = apply + File→Save."""
        if not self._app.dirty and not self._editor_panel.uncommitted_input():
            return "ok"
        m = QMessageBox(self)
        m.setWindowTitle("Unsaved Changes")
        m.setIcon(QMessageBox.Icon.Question)
        m.setText(detail)
        m.setInformativeText(
            "Save writes the current editor into the file and flushes to disk. "
            "Discard continues without saving. Cancel stays here."
        )
        b_save = m.addButton("Save", QMessageBox.ButtonRole.AcceptRole)
        b_discard = m.addButton("Discard", QMessageBox.ButtonRole.DestructiveRole)
        m.addButton(QMessageBox.StandardButton.Cancel)
        m.exec()
        clicked = m.clickedButton()
        if clicked is b_save:
            return "save"
        if clicked is b_discard:
            return "discard"
        return "cancel"

    def _update_title(self):
        name = os.path.basename(self._app.path) if self._app.path else "Untitled"
        dirty = " *" if self._app.dirty else ""
        self.setWindowTitle(f"Page - {name}{dirty}")

    def _status(self, msg: str):
        self._status_bar.showMessage(msg, 5000)

    def closeEvent(self, event: QCloseEvent):
        r = self._offer_save_or_discard("Save before closing?")
        if r == "cancel":
            event.ignore()
        elif r == "save":
            if self._flush_document():
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()
