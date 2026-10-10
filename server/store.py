# -*- coding: utf-8 -*-
"""Хранилище прогресса VibeC: JSON-файл с потокобезопасной атомарной записью.

Файл (data/progress.json) — единственное, что пишет бэкенд на диск. Он живёт
отдельно от папки «обучение» и переживает перезапуск сервера. Отметки,
сделанные в приложении, перекрывают первичные статусы из ПАМЯТЬ.md.
"""
import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path

ALLOWED_STATUS = {"not-started", "in-progress", "done"}
SCHEMA_VERSION = 1


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class ProgressStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self._lock = threading.Lock()
        self._items = {}
        self._load()

    # ------------------------------------------------------------ persistence

    def _load(self) -> None:
        if not self.path.is_file():
            self._items = {}
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            items = data.get("items", {})
            self._items = {k: v for k, v in items.items()
                           if isinstance(v, dict) and v.get("status") in ALLOWED_STATUS}
        except (OSError, ValueError):
            # битый файл не должен ронять сервер — начинаем с пустого прогресса
            self._items = {}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"version": SCHEMA_VERSION, "items": self._items}
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                       encoding="utf-8")
        os.replace(tmp, self.path)  # атомарно: читатель увидит файл целиком

    # ------------------------------------------------------------------ API

    def all(self) -> dict:
        with self._lock:
            return {k: dict(v) for k, v in self._items.items()}

    def set(self, lesson_id: str, status: str, note: str | None = None) -> dict:
        if status not in ALLOWED_STATUS:
            raise ValueError(f"недопустимый статус: {status!r}, "
                             f"разрешены {sorted(ALLOWED_STATUS)}")
        entry = {"status": status, "updated_at": _now(),
                 "note": note or None}
        with self._lock:
            self._items[lesson_id] = entry
            self._save()
        return dict(entry)

    def clear(self, lesson_id: str) -> bool:
        with self._lock:
            if lesson_id not in self._items:
                return False
            del self._items[lesson_id]
            self._save()
            return True
