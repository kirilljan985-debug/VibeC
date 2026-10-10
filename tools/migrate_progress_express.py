# -*- coding: utf-8 -*-
"""Разовая миграция progress.json после переработки экспресс-курсов (10.10.2026).

Было: один курс в папке «экспресс-курс-вайб-кодера», id уроков express-0001…
Стало: ветка «экспресс-курсы/» с курсами-грейдами, id уроков
       <имя-курса>-<номер> (например «вайб-кодер-junior-0001»).

Скрипт переносит отметки старого единственного курса (это junior) на новые id.
Запуск один раз из корня репозитория:  python tools/migrate_progress_express.py
"""
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PROGRESS = REPO / "data" / "progress.json"
OLD_RE = re.compile(r"^express-(\d{4})$")
# старый единственный экспресс-курс = сегодняшний «вайб-кодер-junior»
NEW_PREFIX = "вайб-кодер-junior"


def main() -> int:
    if not PROGRESS.is_file():
        print("progress.json не найден — мигрировать нечего")
        return 0
    data = json.loads(PROGRESS.read_text(encoding="utf-8"))
    items = data.get("items", {})
    moved, kept = {}, 0
    for lesson_id, entry in items.items():
        m = OLD_RE.match(lesson_id)
        if m:
            moved[f"{NEW_PREFIX}-{m.group(1)}"] = entry
        else:
            kept += 1
    if not moved:
        print("Старых id express-NNNN не найдено — миграция не нужна")
        return 0
    data["items"] = {**moved, **{k: v for k, v in items.items() if not OLD_RE.match(k)}}
    tmp = PROGRESS.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(PROGRESS)
    print(f"Перенесено отметок: {len(moved)} → префикс «{NEW_PREFIX}-»; прочих записей: {kept}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
