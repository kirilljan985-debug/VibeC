# -*- coding: utf-8 -*-
"""Тесты авторазрешения папки «обучение» при любом расположении репозитория."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))

from config import resolve_content_root  # noqa: E402


def make_обучение(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "уроки" / "база").mkdir(parents=True, exist_ok=True)
    (root / "уроки" / "база" / "0001-urok.html").write_text(
        "<html><body>урок</body></html>", encoding="utf-8")
    return root


class ResolveContentRootTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.base = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_repo_next_to_обучение(self):
        # прежнее расположение: ~/Desktop/VibeC рядом с ~/Desktop/обучение
        обучение = make_обучение(self.base / "Desktop" / "обучение")
        repo = self.base / "Desktop" / "VibeC"
        repo.mkdir(parents=True)
        self.assertEqual(resolve_content_root(repo), обучение)

    def test_repo_inside_обучение(self):
        # текущее расположение: обучение/VibeC — «обучение» само является предком
        обучение = make_обучение(self.base / "Desktop" / "обучение")
        repo = обучение / "VibeC"
        repo.mkdir(parents=True)
        self.assertEqual(resolve_content_root(repo), обучение)

    def test_repo_deeper_inside_обучение(self):
        # репозиторий ещё глубже: обучение/что-то/VibeC
        обучение = make_обучение(self.base / "обучение")
        repo = обучение / "приложения" / "VibeC"
        repo.mkdir(parents=True)
        self.assertEqual(resolve_content_root(repo), обучение)

    def test_обучение_found_at_second_ancestor(self):
        # ~/рабочее/VibeC и ~/рабочее/обучение — предок-родитель
        обучение = make_обучение(self.base / "рабочее" / "обучение")
        repo = self.base / "рабочее" / "VibeC"
        repo.mkdir(parents=True)
        self.assertEqual(resolve_content_root(repo), обучение)

    def test_not_found_falls_back_to_legacy_default(self):
        # «обучения» нигде нет — прежнее поведение: родитель репозитория
        repo = self.base / "где-то" / "VibeC"
        repo.mkdir(parents=True)
        self.assertEqual(resolve_content_root(repo), repo.parent / "обучение")

    def test_обучение_without_уроки_is_ignored(self):
        # папка с именем «обучение», но без уроков — не источник данных
        (self.base / "Desktop" / "обучение").mkdir(parents=True)
        make_обучение(self.base / "Desktop" / "учёба-настоящая")
        repo = self.base / "Desktop" / "VibeC"
        repo.mkdir()
        # настоящая папка не называется «обучение» и не рядом — легаси-фолбэк
        self.assertEqual(resolve_content_root(repo), repo.parent / "обучение")


if __name__ == "__main__":
    unittest.main()
