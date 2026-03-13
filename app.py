"""
app.py - application state and file I/O

Coordinates between crypto.py and store.py.
Owns the current file path, passphrase, and dirty state.
Does not import any UI code.
"""

import os
from typing import Optional

from crypto import encrypt, decrypt
from store import Store, Entry


class App:
    def __init__(self):
        self._store: Store = Store()
        self._path: Optional[str] = None       # Current file path (None = new unsaved file)
        self._passphrase: Optional[str] = None # Current passphrase
        self._dirty: bool = False              # Unsaved changes?

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def store(self) -> Store:
        return self._store

    @property
    def path(self) -> Optional[str]:
        return self._path

    @property
    def dirty(self) -> bool:
        return self._dirty

    @property
    def has_passphrase(self) -> bool:
        return self._passphrase is not None

    def mark_dirty(self):
        self._dirty = True

    # ------------------------------------------------------------------
    # File operations
    # ------------------------------------------------------------------

    def new(self):
        """Start a new empty file. Clears all state."""
        self._store = Store()
        self._path = None
        self._passphrase = None
        self._dirty = False

    def open(self, path: str, passphrase: str) -> None:
        """
        Open and decrypt an existing .page file.
        Raises RuntimeError on wrong passphrase or corrupt file.
        """
        with open(path, 'r', encoding='ascii') as f:
            armor_text = f.read()

        # Decrypt and deserialize (RuntimeError propagates to caller)
        raw = decrypt(armor_text, passphrase)
        store = Store.from_bytes(raw)

        # Commit state only after successful open
        self._store = store
        self._path = path
        self._passphrase = passphrase
        self._dirty = False

    def save(self) -> None:
        """
        Save to the current file using the current passphrase.
        Requires path and passphrase to be set.
        Raises RuntimeError on failure.
        Uses write-then-replace for safety (avoids partial writes).
        """
        assert self._path is not None, "No file path set"
        assert self._passphrase is not None, "No passphrase set"
        self._write(self._path, self._passphrase)
        self._dirty = False

    def save_as(self, path: str, passphrase: str) -> None:
        """
        Save to a new file with a new passphrase.
        Updates current path and passphrase on success.
        """
        self._write(path, passphrase)
        self._path = path
        self._passphrase = passphrase
        self._dirty = False

    def set_passphrase(self, passphrase: str) -> None:
        """Set passphrase for a new file (called before first save)."""
        self._passphrase = passphrase

    # ------------------------------------------------------------------
    # Entry operations (thin wrappers that also mark dirty)
    # ------------------------------------------------------------------

    def add_entry(self, entry: Entry) -> None:
        self._store.add(entry)
        self.mark_dirty()

    def remove_entry(self, entry: Entry) -> None:
        self._store.remove(entry)
        self.mark_dirty()

    def update_entry(self, entry: Entry) -> None:
        """Call after modifying an entry's fields."""
        entry.touch()
        self.mark_dirty()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _write(self, path: str, passphrase: str) -> None:
        """
        Serialize, encrypt, and write to disk.
        Writes to a temp file first, then renames for atomicity.
        Raises RuntimeError on failure.
        """
        raw = self._store.to_bytes()
        armor = encrypt(raw, passphrase)

        tmp_path = path + '.tmp'
        try:
            with open(tmp_path, 'w', encoding='ascii', newline='\n') as f:
                f.write(armor)
            # Atomic replace
            os.replace(tmp_path, path)
        except Exception:
            # Clean up temp file on failure
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            raise
