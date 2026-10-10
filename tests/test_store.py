# -*- coding: utf-8 -*-
"""Тесты хранилища прогресса: атомарность, валидация, переживание перезапуска."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))

from store import ProgressStore  # noqa: E402


class StoreTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "data" / "progress.json"

    def tearDown(self):
        self._tmp.cleanup()

    def test_set_get_clear(self):
        store = ProgressStore(self.path)
        entry = store.set("base-0001", "done", note="сдал домашку")
        self.assertEqual(entry["status"], "done")
        self.assertIn("base-0001", store.all())
        self.assertTrue(store.clear("base-0001"))
        self.assertFalse(store.clear("base-0001"))
        self.assertEqual(store.all(), {})

    def test_invalid_status_rejected(self):
        store = ProgressStore(self.path)
        with self.assertRaises(ValueError):
            store.set("x", "почти-готово")

    def test_overwrite_keeps_last(self):
        store = ProgressStore(self.path)
        store.set("track-a-0003", "in-progress")
        store.set("track-a-0003", "done")
        self.assertEqual(store.all()["track-a-0003"]["status"], "done")

    def test_survives_reload(self):
        store = ProgressStore(self.path)
        store.set("express-0001", "in-progress", note="смотрю")
        reloaded = ProgressStore(self.path)  # имитация перезапуска сервера
        item = reloaded.all()["express-0001"]
        self.assertEqual(item["status"], "in-progress")
        self.assertEqual(item["note"], "смотрю")

    def test_corrupt_file_starts_empty(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text("{битый json", encoding="utf-8")
        store = ProgressStore(self.path)
        self.assertEqual(store.all(), {})
        store.set("base-0002", "done")  # и запись после этого работает
        self.assertIn("base-0002", ProgressStore(self.path).all())

    def test_concurrent_writes_do_not_lose_data(self):
        import threading
        store = ProgressStore(self.path)
        def worker(i):
            store.set(f"lesson-{i % 5}", "done")
        threads = [threading.Thread(target=worker, args=(i,)) for i in range(25)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        reloaded = ProgressStore(self.path)
        self.assertEqual(len(reloaded.all()), 5)


if __name__ == "__main__":
    unittest.main()
