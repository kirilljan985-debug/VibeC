# -*- coding: utf-8 -*-
"""Тесты сканера: каталог собирается из живой папки без HTTP."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import scanner  # noqa: E402
from fixture import build_fixture  # noqa: E402


class ScannerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.root = build_fixture(Path(cls._tmp.name))
        cls.catalog = scanner.scan_catalog(cls.root)

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_tracks_found_in_order(self):
        ids = [t["id"] for t in self.catalog["tracks"]]
        # база → А → Б известные, затем неизвестная папка становится новым треком
        self.assertEqual(["base", "track-a", "track-b",
                          "track-трек-в-новый"], ids)

    def test_lesson_fields_parsed(self):
        lesson = scanner.find_lesson(self.catalog, "base-0001")
        self.assertIsNotNone(lesson)
        self.assertEqual(lesson["number"], "0001")
        self.assertEqual(lesson["title"], "Как запускается программа")
        self.assertEqual(lesson["kicker"], "Урок 0001 · База · ~20 минут")
        self.assertEqual(lesson["summary"], "Первый урок: что происходит при запуске.")
        self.assertEqual(lesson["interactive"], ["quiz"])
        self.assertTrue(lesson["url"].startswith("/content/уроки/база/"))
        self.assertEqual(lesson["file"], "уроки/база/0001-kak-zapuskaetsya-programma.html")

    def test_readme_and_non_numbered_files_are_not_lessons(self):
        track_b = next(t for t in self.catalog["tracks"] if t["id"] == "track-b")
        self.assertEqual([l["number"] for l in track_b["lessons"]], ["0005"])

    def test_status_seeds_from_memory_md(self):
        seeds = scanner.parse_status_seeds(self.root)
        self.assertEqual(seeds["0001"]["status"], "done")
        self.assertIn("пройден", seeds["0001"]["label"])
        self.assertEqual(seeds["0005"]["status"], "reading")
        self.assertEqual(seeds["0007"]["status"], "next")
        # ❓-строки без номера урока (Stepik) в семена не попадают
        self.assertNotIn("стартовать", seeds)
        # семя приходит в урок
        lesson = scanner.find_lesson(self.catalog, "base-0001")
        self.assertEqual(lesson["seed_status"], "done")

    def test_unknown_track_folder_automatically_included(self):
        lesson = scanner.find_lesson(self.catalog, "track-трек-в-новый-0100")
        self.assertIsNotNone(lesson)
        self.assertEqual(lesson["title"], "Новый трек")

    def test_express_course(self):
        express = self.catalog["express_course"]
        self.assertEqual([l["id"] for l in express["lessons"]], ["express-0001"])
        self.assertIsNotNone(express["intro_url"])
        self.assertIsNotNone(express["glossary_url"])

    def test_references_materials_documents_notes(self):
        ref_ids = [r["id"] for r in self.catalog["references"]]
        self.assertEqual(ref_ids, ["glossary-core", "python-minimum"])
        self.assertEqual(self.catalog["materials"][0]["name"], "progit-ru.pdf")
        docs = {d["id"]: d for d in self.catalog["documents"]}
        self.assertEqual(docs["МИССИЯ"]["title"], "🎯 Миссия")
        self.assertEqual(self.catalog["progress_notes"][0]["number"], "0001")

    def test_foreign_projects_ignored(self):
        all_files = [l["file"] for l in scanner.all_lessons(self.catalog)]
        self.assertFalse(any("rpg-adventure" in f or "python-lab" in f
                             for f in all_files))

    def test_prev_next_navigation(self):
        lesson = scanner.find_lesson(self.catalog, "base-0002")
        self.assertEqual(lesson["prev_id"], "base-0001")
        self.assertEqual(lesson["next_id"], "track-a-0003")
        first = scanner.find_lesson(self.catalog, "base-0001")
        self.assertIsNone(first["prev_id"])

    def test_search_finds_and_snippets(self):
        results = scanner.search_lessons(self.root, self.catalog, "ГЛОССАРИЙ")
        self.assertTrue(any(r["id"] == "track-a-0003" for r in results))
        self.assertIn("…", results[0]["snippet"])
        self.assertEqual(scanner.search_lessons(self.root, self.catalog, "  "), [])
        self.assertEqual(scanner.search_lessons(self.root, self.catalog,
                                                "несуществующее-слово-xyz"), [])

    def test_catalog_counts(self):
        counts = self.catalog["counts"]
        self.assertEqual(counts["tracks"], 4)
        # 2 база + 1 трек А + 1 трек Б + 1 новый трек В
        self.assertEqual(counts["lessons"], 5)
        self.assertEqual(counts["express_lessons"], 1)
        self.assertEqual(counts["documents"], 1)
        self.assertEqual(counts["progress_notes"], 1)

    def test_file_paths_are_posix(self):
        for lesson in scanner.all_lessons(self.catalog):
            self.assertNotIn("\\", lesson["file"], lesson["id"])
            self.assertNotIn("\\", lesson["url"], lesson["id"])


if __name__ == "__main__":
    unittest.main()
