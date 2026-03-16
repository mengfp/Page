#!/usr/bin/env python3
"""
page.py - curses TUI viewer for .page files.

Goals:
- Read a single .page file, decrypt it once using system `age -d`,
  then keep the document in memory.
- Provide a lightweight, read-only UI optimized for small terminals
  (e.g. Termux on Android), but usable on regular Linux/Windows shells.
- Re-use the existing Store/Entry logic without modifying shared code.

Current features:
- Search box at the top (full-text, multi-word AND, same as GUI).
- List of matching entries (index + title + modified time).
- Open an entry to view full details in a simple reader.
- Quit with a single key.

No editing or saving is implemented yet.
"""

import argparse
import curses
import subprocess
import sys
from typing import List

from store import Store, Entry


def _decrypt_with_age(path: str) -> bytes:
    """
    Run `age -d path` and return the decrypted bytes on success.
    Passphrase is handled by age itself via the terminal.
    """
    try:
        proc = subprocess.run(
            ["age", "-d", path],
            stdin=None,  # let age read from the TTY
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except FileNotFoundError as e:
        raise RuntimeError(
            "age command not found. Install age and ensure it is on PATH."
        ) from e

    if proc.returncode != 0:
        msg = proc.stderr.decode("utf-8", errors="ignore").strip()
        raise RuntimeError(f"age -d failed (exit {proc.returncode}):\n{msg}")

    return proc.stdout


def _format_entry_summary(idx: int, entry: Entry, width: int) -> str:
    """Return a single-line summary: index, title, modified."""
    idx_str = f"{idx:3d} "
    when = entry.modified.astimezone().strftime("%Y-%m-%d %H:%M")
    # Reserve space for index + 1 space + date + 1 space
    prefix = idx_str
    suffix = " " + when
    avail = max(0, width - len(prefix) - len(suffix))
    title = entry.title or "(untitled)"
    if len(title) > avail:
        if avail > 1:
            title = title[: avail - 1] + "…"
        else:
            title = ""
    return f"{prefix}{title}{suffix}"


class ListView:
    """
    Top search box + entry list.
    - search_text: current contents of search box
    - displayed: entries matching search_text
    - selected: index into displayed (0-based)
    """

    def __init__(self, store: Store):
        self._store = store
        self.search_text: str = ""
        self.displayed: List[Entry] = list(store.entries)
        self.selected: int = 0

    def _refilter(self) -> None:
        self.displayed = self._store.search(self.search_text)
        if not self.displayed:
            self.selected = 0
        else:
            self.selected = max(0, min(self.selected, len(self.displayed) - 1))

    def handle_key(self, ch: int) -> str | None:
        """
        Handle a keypress.
        Returns:
          - None: stay in list view
          - 'open': enter detail view for current selection
          - 'quit': exit program
        """
        if ch in (curses.KEY_UP, ord("k")):
            if self.displayed:
                self.selected = max(0, self.selected - 1)
            return None
        if ch in (curses.KEY_DOWN, ord("j")):
            if self.displayed:
                self.selected = min(len(self.displayed) - 1, self.selected + 1)
            return None
        if ch in (curses.KEY_ENTER, 10, 13):
            if self.displayed:
                return "open"
            return None
        if ch in (27, ord("q")):  # ESC or q
            return "quit"

        # Backspace keys (terminal-dependent)
        if ch in (curses.KEY_BACKSPACE, 127, 8):
            if self.search_text:
                self.search_text = self.search_text[:-1]
                self._refilter()
            return None

        # Printable ASCII range; keep it simple for now.
        if 32 <= ch <= 126:
            self.search_text += chr(ch)
            self._refilter()
            return None

        return None

    def current_entry(self) -> Entry | None:
        if not self.displayed:
            return None
        if self.selected < 0 or self.selected >= len(self.displayed):
            return None
        return self.displayed[self.selected]

    def draw(self, stdscr: "curses._CursesWindow") -> None:
        max_y, max_x = stdscr.getmaxyx()
        stdscr.erase()

        # Search line
        search_label = "Search: "
        stdscr.addnstr(0, 0, search_label, max_x)
        stdscr.addnstr(0, len(search_label), self.search_text, max_x - len(search_label))

        # List starts at line 1
        list_top = 1
        list_height = max_y - list_top - 1  # leave last line for status
        for i in range(list_height):
            row = list_top + i
            if i >= len(self.displayed):
                # Clear rest of lines
                stdscr.move(row, 0)
                stdscr.clrtoeol()
                continue
            entry = self.displayed[i]
            line = _format_entry_summary(i, entry, max_x)
            if i == self.selected:
                stdscr.attron(curses.A_REVERSE)
                stdscr.addnstr(row, 0, line, max_x)
                stdscr.attroff(curses.A_REVERSE)
            else:
                stdscr.addnstr(row, 0, line, max_x)

        # Status line
        status = "[UP/DOWN] move  [Enter] open  [q] quit"
        stdscr.addnstr(max_y - 1, 0, status, max_x)


class DetailView:
    """Read-only view of a single Entry with scrollable content."""

    def __init__(self, entry: Entry):
        self._entry = entry
        self._scroll: int = 0

    def handle_key(self, ch: int) -> str | None:
        """
        Returns:
          - None: stay in detail view
          - 'back': go back to list
          - 'quit': exit program
        """
        if ch in (ord("q"), 27):  # q or ESC
            return "back"
        if ch in (curses.KEY_UP, ord("k")):
            self._scroll = max(0, self._scroll - 1)
            return None
        if ch in (curses.KEY_DOWN, ord("j")):
            self._scroll += 1
            return None
        if ch in (curses.KEY_PPAGE,):  # Page Up
            self._scroll = max(0, self._scroll - 10)
            return None
        if ch in (curses.KEY_NPAGE,):  # Page Down
            self._scroll += 10
            return None
        return None

    def draw(self, stdscr: "curses._CursesWindow") -> None:
        max_y, max_x = stdscr.getmaxyx()
        stdscr.erase()

        title = self._entry.title or "(untitled)"
        when = self._entry.modified.astimezone().strftime("%Y-%m-%d %H:%M:%S")
        tags = ", ".join(self._entry.tags) if self._entry.tags else "—"

        header_lines = [
            f"Title: {title}",
            f"Date : {when}",
            f"Tags : {tags}",
            "-" * max_x,
        ]

        # Draw header
        row = 0
        for h in header_lines:
            if row >= max_y - 1:
                break
            stdscr.addnstr(row, 0, h, max_x)
            row += 1

        # Content area
        content_lines = self._entry.content.splitlines() or [""]
        visible_height = max_y - row - 1  # leave status line
        start = min(self._scroll, max(0, len(content_lines) - visible_height))
        end = start + visible_height
        for i, line in enumerate(content_lines[start:end]):
            if row + i >= max_y - 1:
                break
            stdscr.addnstr(row + i, 0, line, max_x)

        # Status line
        status = "[UP/DOWN] scroll  [q] back"
        stdscr.addnstr(max_y - 1, 0, status, max_x)


def _main_curses(stdscr: "curses._CursesWindow", store: Store) -> None:
    curses.curs_set(0)  # hide cursor
    stdscr.nodelay(False)
    stdscr.keypad(True)

    list_view = ListView(store)
    current: object = list_view  # either ListView or DetailView

    while True:
        if isinstance(current, ListView):
            current.draw(stdscr)
        elif isinstance(current, DetailView):
            current.draw(stdscr)
        stdscr.refresh()

        ch = stdscr.getch()
        if isinstance(current, ListView):
            action = current.handle_key(ch)
            if action == "quit":
                return
            if action == "open":
                entry = current.current_entry()
                if entry is not None:
                    current = DetailView(entry)
            continue

        if isinstance(current, DetailView):
            action = current.handle_key(ch)
            if action == "back":
                current = list_view
                continue
            if action == "quit":
                return


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Curses TUI viewer for .page files.")
    parser.add_argument("path", help="Path to .page file")
    args = parser.parse_args(argv)

    try:
        raw = _decrypt_with_age(args.path)
        store = Store.from_bytes(raw)
    except Exception as e:
        sys.stderr.write(f"{e}\n")
        return 1

    try:
        curses.wrapper(_main_curses, store)
    except KeyboardInterrupt:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

