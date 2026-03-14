"""Minimal tests: Store JSON round-trip and validation."""
import json
import os
import sys
import unittest
from datetime import datetime, timezone

# Allow `python tests/test_store.py` from repo root (default sys.path is tests/)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from store import Store, Entry
from version import PAGE_DOCUMENT_ID, __version__


class TestStore(unittest.TestCase):
    def test_round_trip(self) -> None:
        s = Store()
        s.entries.append(
            Entry(title="a", tags=["t"], content="body", modified=datetime(2020, 1, 2, 3, 4, 5, tzinfo=timezone.utc))
        )
        raw = s.to_bytes()
        s2 = Store.from_bytes(raw)
        self.assertEqual(len(s2.entries), 1)
        self.assertEqual(s2.entries[0].title, "a")
        self.assertEqual(s2.entries[0].tags, ["t"])
        self.assertEqual(s2.entries[0].content, "body")

    def test_rejects_random_object(self) -> None:
        with self.assertRaises(RuntimeError):
            Store.from_bytes(json.dumps({"x": 1}).encode("utf-8"))

    def test_rejects_wrong_id(self) -> None:
        with self.assertRaises(RuntimeError):
            Store.from_bytes(
                json.dumps(
                    {
                        "id": "00000000-0000-0000-0000-000000000000",
                        "version": __version__,
                        "entries": [],
                    }
                ).encode("utf-8")
            )

    def test_rejects_missing_version(self) -> None:
        with self.assertRaises(RuntimeError):
            Store.from_bytes(
                json.dumps({"id": PAGE_DOCUMENT_ID, "entries": []}).encode("utf-8")
            )

    def test_rejects_plain_array_root(self) -> None:
        legacy = [{"title": "t", "tags": [], "content": "", "modified": "2020-01-01T00:00:00+00:00"}]
        with self.assertRaises(RuntimeError):
            Store.from_bytes(json.dumps(legacy).encode("utf-8"))

    def test_envelope_round_trip(self) -> None:
        raw = Store.from_bytes(
            json.dumps(
                {
                    "id": PAGE_DOCUMENT_ID,
                    "version": __version__,
                    "entries": [
                        {
                            "title": "a",
                            "tags": ["x"],
                            "content": "c",
                            "modified": "2021-02-03T04:05:06+00:00",
                        }
                    ],
                }
            ).encode("utf-8")
        )
        self.assertEqual(len(raw.entries), 1)
        out = raw.to_bytes()
        self.assertIn(PAGE_DOCUMENT_ID.encode("ascii"), out)
        self.assertIn(b'"entries"', out)
        self.assertIn(__version__.encode("ascii"), out)

    def test_invalid_json(self) -> None:
        with self.assertRaises(RuntimeError):
            Store.from_bytes(b"not json")

    def test_search_empty_keyword_returns_all(self) -> None:
        s = Store()
        s.entries.append(Entry(title="x"))
        self.assertEqual(len(s.search("")), 1)


if __name__ == "__main__":
    unittest.main()
