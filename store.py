"""
store.py - data model, JSON serialization, and search

Data structure (in memory):
    A Store contains a list of Entry objects.
    Each Entry has: title, tags, modified (ISO 8601), content (free text).

Persistence:
    Serialized as JSON, encrypted by crypto.py.
    On disk (after decrypt): { id, version, entries }. id = PAGE_DOCUMENT_ID;
    version = version.__version__ (same as Page app version—no separate format number).

Search:
    All search is performed in-memory after decryption.
"""

import json
from datetime import datetime, timezone
from typing import Any, Optional

from version import PAGE_DOCUMENT_ID, __version__

# Limits (reject oversize / odd types)
_MAX_ENTRIES = 50_000
_MAX_TITLE_LEN = 20_000
_MAX_TAGS_PER_ENTRY = 2_000
_MAX_TAG_LEN = 500
_MAX_CONTENT_BYTES = 20 * 1024 * 1024  # 20 MiB UTF-8 per entry


class Entry:
    def __init__(
        self,
        title: str = '',
        tags: Optional[list[str]] = None,
        content: str = '',
        modified: Optional[datetime] = None,
    ):
        self.title = title
        self.tags: list[str] = tags if tags is not None else []
        self.content = content
        self.modified: datetime = modified if modified is not None else _now()

    def touch(self):
        """Update modified timestamp to now."""
        self.modified = _now()

    def to_dict(self) -> dict:
        return {
            'title': self.title,
            'tags': self.tags,
            'modified': self.modified.isoformat(),
            'content': self.content,
        }

    @staticmethod
    def from_dict(d: dict) -> "Entry":
        for key in ("title", "tags", "content", "modified"):
            if key not in d:
                raise RuntimeError(f"Entry missing required key {key!r}")
        if not isinstance(d["title"], str):
            raise RuntimeError("Entry title must be a string")
        if not isinstance(d["tags"], list) or not all(
            isinstance(t, str) for t in d["tags"]
        ):
            raise RuntimeError("Entry tags must be a list of strings")
        if not isinstance(d["content"], str):
            raise RuntimeError("Entry content must be a string")
        if not isinstance(d["modified"], str) or not d["modified"].strip():
            raise RuntimeError("Entry modified must be a non-empty ISO date string")
        title = d["title"]
        tags = list(d["tags"])
        content = d["content"]
        try:
            modified = datetime.fromisoformat(d["modified"])
        except ValueError as e:
            raise RuntimeError("Entry modified is not valid ISO-8601") from e
        if len(title) > _MAX_TITLE_LEN:
            raise RuntimeError("Entry title too long")
        if len(tags) > _MAX_TAGS_PER_ENTRY:
            raise RuntimeError("Entry has too many tags")
        if any(len(t) > _MAX_TAG_LEN for t in tags):
            raise RuntimeError("Entry tag too long")
        if len(content.encode("utf-8")) > _MAX_CONTENT_BYTES:
            raise RuntimeError("Entry content too large")
        return Entry(title=title, tags=tags, content=content, modified=modified)

    def matches(self, keyword: str) -> bool:
        """Full-text search: title + tags + content."""
        kw = keyword.lower()
        return (
            kw in self.title.lower()
            or kw in self.content.lower()
            or any(kw in tag.lower() for tag in self.tags)
        )


class Store:
    def __init__(self):
        self.entries: list[Entry] = []

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_bytes(self) -> bytes:
        """Serialize: id + version (__version__) + entries—no extra format version."""
        envelope = {
            "id": PAGE_DOCUMENT_ID,
            "version": __version__,
            "entries": [entry.to_dict() for entry in self.entries],
        }
        return json.dumps(envelope, ensure_ascii=False, indent=2).encode("utf-8")

    @staticmethod
    def from_bytes(raw: bytes) -> "Store":
        """Deserialize Page envelope; version is whichever Page build wrote the file."""
        try:
            data: Any = json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            raise RuntimeError(f"Invalid JSON: {e}") from e

        if not isinstance(data, dict):
            raise RuntimeError(
                "Not a Page file: root must be an object with id, version, entries"
            )
        if data.get("id") != PAGE_DOCUMENT_ID:
            raise RuntimeError(
                "Not a Page file: id does not match Page document type "
                f"(expected {PAGE_DOCUMENT_ID!r})"
            )
        if not isinstance(data.get("version"), str) or not str(data.get("version")).strip():
            raise RuntimeError(
                "Not a Page file: version must be a non-empty string (Page app version)"
            )
        if not isinstance(data.get("entries"), list):
            raise RuntimeError("Not a Page file: entries must be a list")
        items = data["entries"]

        if len(items) > _MAX_ENTRIES:
            raise RuntimeError("Too many entries in file")

        store = Store()
        for i, item in enumerate(items):
            if not isinstance(item, dict):
                raise RuntimeError(f"Entry at index {i} is not an object")
            try:
                store.entries.append(Entry.from_dict(item))
            except RuntimeError as e:
                raise RuntimeError(f"Entry at index {i}: {e}") from e
        return store

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def add(self, entry: Entry) -> None:
        self.entries.append(entry)

    def remove(self, entry: Entry) -> None:
        self.entries.remove(entry)

    # ------------------------------------------------------------------
    # Search and filter
    # ------------------------------------------------------------------

    def search(self, keyword: str) -> list[Entry]:
        """Full-text search across title, tags, and content."""
        if not keyword:
            return list(self.entries)
        return [e for e in self.entries if e.matches(keyword)]

    def filter_by_tag(self, tag: str) -> list[Entry]:
        """Return entries that have the given tag."""
        return [e for e in self.entries if tag in e.tags]

    def all_tags(self) -> list[str]:
        """Return sorted list of all unique tags."""
        tags = set()
        for entry in self.entries:
            tags.update(entry.tags)
        return sorted(tags)

    def sorted_by_modified(self, entries: Optional[list[Entry]] = None, descending: bool = True) -> list[Entry]:
        """Sort entries by modified date."""
        source = entries if entries is not None else self.entries
        return sorted(source, key=lambda e: e.modified, reverse=descending)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _now() -> datetime:
    return datetime.now(timezone.utc)
