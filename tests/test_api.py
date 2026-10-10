# -*- coding: utf-8 -*-
"""Тесты API: сервер на живом сокете (порт 0), фикстура вместо реальной папки."""
import json
import sys
import tempfile
import unittest
import urllib.request
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import app  # noqa: E402
from fixture import build_fixture  # noqa: E402


def fetch(base: str, path: str, method: str = "GET", payload: dict | None = None):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(base + path, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as resp:
            body = resp.read()
            ctype = resp.headers.get("Content-Type", "")
            return resp.status, ctype, body
    except urllib.error.HTTPError as err:
        try:
            return err.code, err.headers.get("Content-Type", ""), err.read()
        finally:
            err.close()


def jbody(body: bytes) -> dict:
    return json.loads(body.decode("utf-8"))


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        tmp = Path(cls._tmp.name)
        cls.content_root = build_fixture(tmp / "обучение")
        cls.progress_file = tmp / "data" / "progress.json"
        cls.front_dir = tmp / "front"  # пусто — сервер должен отдать заглушку
        cls.server = app.create_server("127.0.0.1", 0, cls.content_root,
                                       cls.front_dir, cls.progress_file)
        cls.base = f"http://127.0.0.1:{cls.server.server_address[1]}"
        import threading
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls._tmp.cleanup()

    # ------------------------------------------------------------------ API

    def test_catalog_endpoint(self):
        status, ctype, body = fetch(self.base, "/api/catalog")
        self.assertEqual(status, 200)
        self.assertIn("application/json", ctype)
        catalog = jbody(body)
        self.assertEqual(catalog["api"], "vibec")
        self.assertGreaterEqual(catalog["counts"]["lessons"], 4)

    def test_lesson_endpoint_found_and_not_found(self):
        status, _, body = fetch(self.base, "/api/lesson/base-0002")
        self.assertEqual(status, 200)
        lesson = jbody(body)
        self.assertEqual(lesson["title"], "Терминал — главный инструмент")
        self.assertEqual(lesson["prev_id"], "base-0001")
        self.assertIsNone(lesson["progress"])

        status, _, body = fetch(self.base, "/api/lesson/nope-9999")
        self.assertEqual(status, 404)
        self.assertIn("не найден", jbody(body)["error"])

    def test_progress_roundtrip_and_persistence(self):
        # поставить
        status, _, body = fetch(self.base, "/api/progress", "POST",
                                {"lesson_id": "base-0001", "status": "done"})
        self.assertEqual(status, 200)
        self.assertEqual(jbody(body)["progress"]["status"], "done")
        # прочитать
        status, _, body = fetch(self.base, "/api/progress")
        self.assertIn("base-0001", jbody(body)["items"])
        # урок видит свою отметку
        _, _, body = fetch(self.base, "/api/lesson/base-0001")
        self.assertEqual(jbody(body)["progress"]["status"], "done")
        # файл записан на диск
        saved = json.loads(self.progress_file.read_text(encoding="utf-8"))
        self.assertIn("base-0001", saved["items"])
        # недопустимый статус → 400
        status, _, body = fetch(self.base, "/api/progress", "POST",
                                {"lesson_id": "base-0001", "status": "super"})
        self.assertEqual(status, 400)
        # снять
        status, _, body = fetch(self.base, "/api/progress", "POST",
                                {"lesson_id": "base-0001", "status": None})
        self.assertEqual(status, 200)
        self.assertTrue(jbody(body)["cleared"])
        self.assertNotIn("base-0001", jbody(fetch(self.base, "/api/progress")[2])["items"])

    def test_progress_bad_requests(self):
        status, _, _ = fetch(self.base, "/api/progress", "POST", {"status": "done"})
        self.assertEqual(status, 400)
        status, _, _ = fetch(self.base, "/api/progress", "POST", "не-объект")
        self.assertEqual(status, 400)

    def test_progress_unknown_lesson_rejected_on_set_allowed_on_clear(self):
        # постановка отметки для урока не из каталога → 404 (защита от сирот в json)
        status, _, body = fetch(self.base, "/api/progress", "POST",
                                {"lesson_id": "ghost-9999", "status": "done"})
        self.assertEqual(status, 404)
        self.assertIn("отсутствует в каталоге", jbody(body)["error"])
        # снятие разрешено: так убираются осиротевшие записи
        status, _, _ = fetch(self.base, "/api/progress", "POST",
                             {"lesson_id": "ghost-9999", "status": None})
        self.assertEqual(status, 200)

    def test_search_endpoint(self):
        status, _, body = fetch(self.base, "/api/search?q=%D0%B3%D0%BB%D0%BE%D1%81%D1%81")
        self.assertEqual(status, 200)
        data = jbody(body)
        self.assertGreaterEqual(data["count"], 1)
        self.assertTrue(all("snippet" in r for r in data["results"]))

    def test_meta_endpoint(self):
        status, _, body = fetch(self.base, "/api/meta")
        self.assertEqual(status, 200)
        meta = jbody(body)
        self.assertTrue(meta["content_root_exists"])
        self.assertFalse(meta["front_present"])  # front/ пуст — заглушка
        self.assertEqual(meta["counts"]["tracks"], 4)

    def test_unknown_endpoint_404(self):
        status, _, _ = fetch(self.base, "/api/nope")
        self.assertEqual(status, 404)

    # -------------------------------------------------------------- статика

    def test_content_serves_lesson_with_utf8(self):
        path = "/content/%D1%83%D1%80%D0%BE%D0%BA%D0%B8/%D0%B1%D0%B0%D0%B7%D0%B0/" \
               "0001-kak-zapuskaetsya-programma.html"
        status, ctype, body = fetch(self.base, path)
        self.assertEqual(status, 200)
        self.assertIn("text/html", ctype)
        self.assertIn("charset=utf-8", ctype)
        self.assertIn("Как запускается программа", body.decode("utf-8"))

    def test_content_blocks_traversal_and_hidden(self):
        # попытка выйти за корень
        secret = self.content_root.parent / "secret.txt"
        secret.write_text("секрет", encoding="utf-8")
        try:
            status, _, _ = fetch(self.base, "/content/..%2Fsecret.txt")
            self.assertEqual(status, 404)
        finally:
            secret.unlink()
        # скрытые файлы/папки не отдаём
        hidden_dir = self.content_root / ".git"
        hidden_dir.mkdir(exist_ok=True)
        (hidden_dir / "config").write_text("x", encoding="utf-8")
        status, _, _ = fetch(self.base, "/content/.git/config")
        self.assertEqual(status, 404)

    def test_placeholder_when_no_front(self):
        status, ctype, body = fetch(self.base, "/")
        self.assertEqual(status, 200)
        self.assertIn("text/html", ctype)
        self.assertIn("VibeC", body.decode("utf-8"))

    def test_front_index_replaces_placeholder(self):
        (self.front_dir).mkdir(exist_ok=True)
        index = self.front_dir / "index.html"
        index.write_text("<html><body>FRONT-OK</body></html>", encoding="utf-8")
        self.addCleanup(index.unlink)  # не ломать соседние тесты порядком выполнения
        status, _, body = fetch(self.base, "/")
        self.assertEqual(status, 200)
        self.assertIn("FRONT-OK", body.decode("utf-8"))
        # статика фронта тоже отдаётся
        app_js = self.front_dir / "app.js"
        app_js.write_text("console.log(1)", encoding="utf-8")
        self.addCleanup(app_js.unlink)
        status, ctype, body = fetch(self.base, "/app.js")
        self.assertEqual(status, 200)
        self.assertIn("javascript", ctype)

    def test_front_static_cannot_escape(self):
        status, _, _ = fetch(self.base, "/..%2Fserver%2Fapp.py")
        self.assertEqual(status, 404)


if __name__ == "__main__":
    unittest.main()
