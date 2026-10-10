# -*- coding: utf-8 -*-
"""Конфигурация VibeC: пути и параметры запуска.

Все значения можно переопределить переменными окружения:
  VIBEC_CONTENT_ROOT  — путь к папке «обучение» (источник данных)
  VIBEC_PORT          — порт HTTP-сервера (по умолчанию 8765)
  VIBEC_HOST          — интерфейс (по умолчанию 127.0.0.1 — наружу не торчим)
  VIBEC_OPEN_BROWSER  — 1: открыть браузер после старта (использует запуск.bat)
"""
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# По умолчанию папка «обучение» ищется рядом с репозиторием (оба на рабочем столе).
DEFAULT_CONTENT_ROOT = REPO_ROOT.parent / "обучение"

DATA_DIR = REPO_ROOT / "data"
FRONT_DIR = REPO_ROOT / "front"
PROGRESS_FILE = DATA_DIR / "progress.json"

HOST = os.environ.get("VIBEC_HOST", "127.0.0.1")
PORT = int(os.environ.get("VIBEC_PORT", "8765"))
OPEN_BROWSER = os.environ.get("VIBEC_OPEN_BROWSER", "") == "1"


def content_root() -> Path:
    """Актуальный корень контента: env-переменная сильнее значения по умолчанию."""
    override = os.environ.get("VIBEC_CONTENT_ROOT", "").strip()
    return Path(override) if override else DEFAULT_CONTENT_ROOT
