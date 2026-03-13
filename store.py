"""
store.py - data model, JSON serialization, and search

Data structure (in memory):
    A Store contains a list of Entry objects.
    Each Entry has: title, tags, modified (ISO 8601), content (free text).

Persistence:
    Serialized as JSON, encrypted by crypto.py.
    The Store does not know about encryption; it only produces/consumes bytes.

Search:
    All search is performed in-memory after decryption.
"""

import json
from datetime import datetime, timezone
from typing import Optional


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
    def from_dict(d: dict) -> 'Entry':
        return Entry(
            title=d.get('title', ''),
            tags=d.get('tags', []),
            content=d.get('content', ''),
            modified=datetime.fromisoformat(d['modified']),
        )

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
        """Serialize store to JSON bytes (UTF-8)."""
        data = [entry.to_dict() for entry in self.entries]
        return json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8')

    @staticmethod
    def from_bytes(raw: bytes) -> 'Store':
        """Deserialize store from JSON bytes."""
        data = json.loads(raw.decode('utf-8'))
        store = Store()
        store.entries = [Entry.from_dict(d) for d in data]
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
