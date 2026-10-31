# -*- coding: utf-8 -*-
"""Конфигурация VibeC: пути и параметры запуска.

Все значения можно переопределить переменными окружения:
  VIBEC_CONTENT_ROOT  — путь к папке «обучение» (источник данных)
  VIBEC_PORT          — порт HTTP-сервера (по умолчанию 8765)
  VIBEC_HOST          — интерфейс (по умолчанию 127.0.0.1 — наружу не торчим)
  VIBEC_OPEN_BROWSER  — 1: открыть браузер после старта (использует запуск.bat)
"""
import os
import sys
from pathlib import Path

if getattr(sys, "frozen", False):
    # режим exe (PyInstaller): __file__ указывает во временную папку распаковки,
    # поэтому репозиторий ищем рядом с самим exe — exe живёт в корне VibeC
    REPO_ROOT = Path(sys.executable).resolve().parent
else:
    REPO_ROOT = Path(__file__).resolve().parents[1]

DATA_DIR = REPO_ROOT / "data"
FRONT_DIR = REPO_ROOT / "front"
PROGRESS_FILE = DATA_DIR / "progress.json"

HOST = os.environ.get("VIBEC_HOST", "127.0.0.1")
PORT = int(os.environ.get("VIBEC_PORT", "8765"))
OPEN_BROWSER = os.environ.get("VIBEC_OPEN_BROWSER", "") == "1"

# Автостоп: сервер завершается сам после N минут без запросов (0 — никогда).
# У exe консоль скрыта, поэтому бездействующий экземпляр не должен висеть вечно.
IDLE_EXIT_MINUTES = int(os.environ.get("VIBEC_IDLE_EXIT_MINUTES", "30"))


def resolve_content_root(repo_root: Path | None = None) -> Path:
    """Найти папку «обучение» относительно репозитория.

    Работает при любом расположении репозитория: рядом с «обучением»
    (~/Desktop/VibeC), внутри него (обучение/VibeC) или уровнем выше.
    Идём вверх по дереву: у каждого предка проверяем его подпапку
    «обучение» и его самого (по характерной подпапке «уроки»).
    """
    repo = Path(repo_root) if repo_root is not None else REPO_ROOT
    for ancestor in list(repo.parents)[:4]:
        candidate = ancestor / "обучение"
        if candidate.is_dir() and (candidate / "уроки").is_dir():
            return candidate
        if ancestor.name == "обучение" and (ancestor / "уроки").is_dir():
            return ancestor
    return repo.parent / "обучение"  # не нашли — прежнее место по умолчанию


def content_root() -> Path:
    """Актуальный корень контента: env-переменная сильнее авторазрешения."""
    override = os.environ.get("VIBEC_CONTENT_ROOT", "").strip()
    return Path(override) if override else resolve_content_root()
