"""Minimal tests: Store JSON round-trip and validation."""
import json
import unittest
from datetime import datetime, timezone

from store import Store, Entry


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

    def test_invalid_not_array(self) -> None:
        with self.assertRaises(RuntimeError):
            Store.from_bytes(json.dumps({"x": 1}).encode("utf-8"))

    def test_invalid_json(self) -> None:
        with self.assertRaises(RuntimeError):
            Store.from_bytes(b"not json")

    def test_search_empty_keyword_returns_all(self) -> None:
        s = Store()
        s.entries.append(Entry(title="x"))
        self.assertEqual(len(s.search("")), 1)


if __name__ == "__main__":
    unittest.main()
