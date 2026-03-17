#!/usr/bin/env python3
"""
page.py - curses TUI viewer for .page files.

Goals:
- Read a single .page file, decrypt it once using system `age -d`,
  then keep the document in memory.
- Provide a lightweight, read-only UI optimized for small terminals
  (e.g. Termux on Android), but usable on regular Linux/Windows shells.
- Re-use the existing Store/Entry logic without modifying shared code.

This script is intentionally simple on the CLI side:
- No -h/--help flags or subcommands.
- If no arguments are given, print product info and usage then exit(0).
- If one or more arguments are given, the first is treated as the .page path.
"""

import curses
import locale
import subprocess
import sys
import unicodedata
from typing import List

from store import Store, Entry
from version import APP_NAME, __version__


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


def _col_width(s: str) -> int:
    """Return the display width of s in terminal columns."""
    w = 0
    for c in s:
        w += 2 if unicodedata.east_asian_width(c) in ("W", "F") else 1
    return w


def _truncate_to_cols(s: str, max_cols: int) -> str:
    """Return the longest prefix of s whose display width <= max_cols."""
    w = 0
    for i, c in enumerate(s):
        cw = 2 if unicodedata.east_asian_width(c) in ("W", "F") else 1
        if w + cw > max_cols:
            return s[:i]
        w += cw
    return s


def _format_entry_summary(idx: int, entry: Entry, safe_cols: int) -> str:
    """
    Single-line summary: index + title + modified date.
    safe_cols is the usable line width (already excludes the right safety margin).
    Title is truncated by display columns so the line fits.
    """
    prefix = f"{idx:3d} "
    suffix = " " + entry.modified.astimezone().strftime("%Y-%m-%d %H:%M")
    # Both prefix and suffix are pure ASCII, so len() == col width.
    avail = max(0, safe_cols - len(prefix) - len(suffix))
    title = entry.title or "(untitled)"
    title_trunc = _truncate_to_cols(title, avail - 2)  # reserve 2 cols for "…"
    if _col_width(title_trunc) < _col_width(title):
        title_trunc += "…"
    return f"{prefix}{title_trunc}{suffix}"


def _addstr_safe(stdscr: "curses._CursesWindow", row: int, col: int, s: str) -> None:
    """addstr wrapper that silently ignores curses errors (e.g. bottom-right corner)."""
    try:
        stdscr.addstr(row, col, s)
    except curses.error:
        pass


class ListView:
    """
    Entry list above, search line at bottom (near soft keyboard).
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

    def handle_key(self, ch: int | str) -> str | None:
        """
        Handle a keypress. get_wch() returns str for printable chars, int for special keys.
        Returns:
          - None: stay in list view
          - 'open': enter detail view for current selection
          - 'quit': exit program
        """
        # Printable character (including Chinese) from get_wch()
        if isinstance(ch, str):
            if ch == "\x1b":          # ESC returned as string by some terminals
                return "quit"
            if ch in ("\n", "\r"):    # Enter returned as string by some terminals
                if self.displayed:
                    return "open"
                return None
            if ch >= " ":             # skip other control characters
                self.search_text += ch
                self._refilter()
            return None

        # Special / control keys returned as int
        if ch == curses.KEY_UP:
            if self.displayed:
                self.selected = max(0, self.selected - 1)
            return None
        if ch == curses.KEY_DOWN:
            if self.displayed:
                self.selected = min(len(self.displayed) - 1, self.selected + 1)
            return None
        if ch in (curses.KEY_ENTER, 10, 13):
            if self.displayed:
                return "open"
            return None
        if ch == 27:                  # ESC as int
            return "quit"
        if ch in (curses.KEY_BACKSPACE, 127, 8):
            if self.search_text:
                self.search_text = self.search_text[:-1]
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

        # One-column safety margin: never write to column max_x-1 to avoid
        # the ncurses bottom-right-corner ERR (cursor would move off-screen).
        safe_cols = max_x - 1

        # List occupies rows 0 .. max_y-2; search line at bottom (max_y-1)
        list_height = max_y - 1
        scroll_offset = min(
            max(0, self.selected - list_height + 1),
            max(0, len(self.displayed) - list_height),
        )
        for i in range(list_height):
            idx = scroll_offset + i
            if idx >= len(self.displayed):
                stdscr.move(i, 0)
                stdscr.clrtoeol()
                continue
            entry = self.displayed[idx]
            line = _truncate_to_cols(_format_entry_summary(idx, entry, safe_cols), safe_cols)
            if idx == self.selected:
                stdscr.attron(curses.A_REVERSE)
                _addstr_safe(stdscr, i, 0, line)
                stdscr.attroff(curses.A_REVERSE)
            else:
                _addstr_safe(stdscr, i, 0, line)

        # Search line at bottom
        search_label = "Search: "
        # Available cols for user text: exclude label and safety margin
        avail_cols = max(0, safe_cols - len(search_label))
        display_text = _truncate_to_cols(self.search_text, avail_cols)
        _addstr_safe(stdscr, max_y - 1, 0, search_label)
        _addstr_safe(stdscr, max_y - 1, len(search_label), display_text)


class DetailView:
    """Read-only view of a single Entry with scrollable content."""

    def __init__(self, entry: Entry):
        self._entry = entry
        self._scroll: int = 0

    def handle_key(self, ch: int | str) -> str | None:
        """
        Returns:
          - None: stay in detail view
          - 'back': go back to list
        """
        if isinstance(ch, str):
            if ch == "\x1b":          # ESC returned as string by some terminals
                return "back"
            return None
        if ch == 27:                  # ESC as int
            return "back"
        if ch == curses.KEY_UP:
            self._scroll = max(0, self._scroll - 1)
            return None
        if ch == curses.KEY_DOWN:
            self._scroll += 1
            return None
        if ch == curses.KEY_PPAGE:
            self._scroll = max(0, self._scroll - 10)
            return None
        if ch == curses.KEY_NPAGE:
            self._scroll += 10
            return None
        return None

    def draw(self, stdscr: "curses._CursesWindow") -> None:
        max_y, max_x = stdscr.getmaxyx()
        stdscr.erase()

        safe_cols = max_x - 1

        title = self._entry.title or "(untitled)"
        when = self._entry.modified.astimezone().strftime("%Y-%m-%d %H:%M:%S")
        tags = ", ".join(self._entry.tags) if self._entry.tags else "—"

        header_lines = [
            f"Title: {title}",
            f"Date : {when}",
            f"Tags : {tags}",
            "-" * safe_cols,
        ]

        row = 0
        for h in header_lines:
            if row >= max_y:
                break
            _addstr_safe(stdscr, row, 0, _truncate_to_cols(h, safe_cols))
            row += 1

        content_lines = self._entry.content.splitlines() or [""]
        visible_height = max_y - row
        start = min(self._scroll, max(0, len(content_lines) - visible_height))
        for i, line in enumerate(content_lines[start : start + visible_height]):
            if row + i >= max_y:
                break
            _addstr_safe(stdscr, row + i, 0, _truncate_to_cols(line, safe_cols))


def _main_curses(stdscr: "curses._CursesWindow", store: Store) -> None:
    curses.curs_set(0)
    stdscr.nodelay(False)
    stdscr.keypad(True)
    # ESC delay 250ms: responsive enough, safe for remote/slow terminals
    curses.set_escdelay(250)

    list_view = ListView(store)
    current: object = list_view

    while True:
        if isinstance(current, ListView):
            current.draw(stdscr)
        elif isinstance(current, DetailView):
            current.draw(stdscr)
        stdscr.refresh()

        ch = stdscr.get_wch()
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


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    if not argv:
        sys.stdout.write(f"{APP_NAME} TUI viewer (version {__version__})\n")
        sys.stdout.write("https://github.com/mengfp/page\n")
        sys.stdout.write("Usage:\n")
        sys.stdout.write("  python page.py PATH_TO_FILE.page\n")
        sys.stdout.write("  (or make page.py executable and run ./page.py PATH)\n")
        return 0

    path = argv[0]

    try:
        raw = _decrypt_with_age(path)
        store = Store.from_bytes(raw)
    except Exception as e:
        sys.stderr.write(f"{e}\n")
        return 1

    # UTF-8 locale required for get_wch() to return complete Unicode characters
    try:
        locale.setlocale(locale.LC_ALL, "")
    except locale.Error:
        pass

    try:
        curses.wrapper(_main_curses, store)
    except KeyboardInterrupt:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
