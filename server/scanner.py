# -*- coding: utf-8 -*-
"""Сканер папки «обучение» → структурированный каталог для фронта.

Принцип: папка «обучение» — единственный источник правды. Сканер ничего не
кэширует и не копирует; каждый вызов scan_catalog() читает живую папку,
поэтому новый урок, положенный преподавателем, появляется в приложении сам.

Чистый модуль без HTTP: тестируется отдельно от сервера (см. tests/).
"""
import html as html_mod
import re
from datetime import datetime, timezone
from pathlib import Path

# Подпапки корня, которые не являются разделами курса
SKIP_DIRS = {"rpg-adventure", "python-lab", "компоненты", ".git"}

# Известные треки: id → (папка, человекочитаемое название, описание)
KNOWN_TRACKS = {
    "база": ("base", "База · общие уроки",
             "Уроки, общие для обоих треков: как запускается программа, терминал"),
    "трек-А-ии-инженерия": ("track-a", "Трек А · ИИ-инженерия и вайб-кодинг",
                            "Промпт → дифф → ревью → итерация; работа с агентом"),
    "трек-Б-питон": ("track-b", "Трек Б · Python",
                     "Понятие → практика руками → квиз → домашка Stepik"),
}

EXPRESS_DIR = "экспресс-курсы"  # ветка экспресс-курсов: каждая подпапка — отдельный курс
GAME_DEV_FILE = "разработка-игры.md"  # раздел «Разработка игры» в корне обучения
LESSON_RE = re.compile(r"^(\d{4})-")  # имена уроков: 0001-kak-...

# Статусы уроков из таблицы «Статус» в обучение/ПАМЯТЬ.md (первичный посев;
# отметки пользователя в data/progress.json их перекрывают — см. store.py)
STATUS_MAP = {"✅": "done", "📖": "reading", "⏳": "next", "❓": "planned"}
SEED_RE = re.compile(r"^\|\s*(\d{4})\b.*?\|\s*(✅|📖|⏳|❓)\s*([^|]*?)\s*\|", re.M)

REF_DESCRIPTIONS = {
    "glossary-core": "Ядерный глоссарий курса — читать после урока 0003",
    "glossary-interactive": "Интерактивный глоссарий: 101 термин, отметки «знаю / ещё учу»",
    "glossary-express-courses": "Глоссарий ветки «Вайб-кодер»: 90 терминов по всем грейдам (junior/middle/senior)",
    "python-minimum": "Копилка понятий Python — пополняется после каждого урока трека Б",
}


# ---------------------------------------------------------------- разбор HTML

def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _tag_text(fragment: str) -> str:
    """Текст HTML-фрагмента: без тегов, с раскрытыми сущностями, в одну строку."""
    text = re.sub(r"<[^>]+>", " ", fragment)
    text = html_mod.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _match(html: str, pattern: str) -> str:
    m = re.search(pattern, html, re.S)
    return _tag_text(m.group(1)) if m else ""


def parse_lesson_html(html: str) -> dict:
    """Достаёт из HTML урока метаданные: заголовки, kicker, описание, интерактив."""
    title = _match(html, r"<title[^>]*>(.*?)</title>")
    h1 = _match(html, r"<h1[^>]*>(.*?)</h1>")
    kicker = _match(html, r'class="lesson-kicker"[^>]*>(.*?)</div>')
    summary = _match(html, r'class="lesson-meta"[^>]*>(.*?)</p>')
    interactive = [name for name, marker in
                   (("quiz", "quiz.js"), ("flashcards", "flashcards.js"),
                    ("glossary", "glossary-app.js")) if marker in html]
    return {
        "title": h1 or title,
        "page_title": title,
        "kicker": kicker,
        "summary": summary,
        "interactive": interactive,
    }


def plain_text(html: str) -> str:
    """Весь видимый текст страницы — для полнотекстового поиска."""
    html = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.S | re.I)
    return _tag_text(html)


# ------------------------------------------------------- статусы из ПАМЯТЬ.md

def parse_status_seeds(root: Path) -> dict:
    """{'0001': {'status': 'done', 'label': 'пройден'}, ...} из обучение/ПАМЯТЬ.md."""
    memory = root / "ПАМЯТЬ.md"
    if not memory.is_file():
        return {}
    seeds = {}
    for m in SEED_RE.finditer(_read(memory)):
        number, emoji, label = m.group(1), m.group(2), m.group(3)
        seeds[number] = {"status": STATUS_MAP[emoji], "label": label}
    return seeds


# ------------------------------------------------------------- сбор разделов

def _url(rel_path: str) -> str:
    """URL контента: /content/<путь внутри обучения>, posix-разделители."""
    return "/content/" + rel_path.replace("\\", "/")


def _rel(path: Path, root: Path) -> str:
    """Путь файла относительно корня обучения — всегда posix ('уроки/база/…')."""
    return path.relative_to(root).as_posix()


def _make_track(folder_name: str) -> dict:
    if folder_name in KNOWN_TRACKS:
        track_id, title, description = KNOWN_TRACKS[folder_name]
    else:  # новая папка уроков появляется без правки кода
        track_id = "track-" + re.sub(r"\s+", "-", folder_name.lower())
        title = "Трек · " + folder_name
        description = ""
    return {"id": track_id, "folder": folder_name, "title": title,
            "description": description, "lessons": [], "files": []}


def _scan_game_dev(root: Path) -> dict | None:
    """Раздел «Разработка игры» — поэтапная разработка «Пепла» (разработка-игры.md)."""
    path = root / GAME_DEV_FILE
    if not path.is_file():
        return None
    return {"id": "game-dev", "title": _md_title(path),
            "file": _rel(path, root), "url": _url(_rel(path, root))}


def _collect_track_lessons(root: Path, track: dict, seeds: dict) -> None:
    track_dir = root / "уроки" / track["folder"]
    if not track_dir.is_dir():
        return
    for path in sorted(track_dir.iterdir()):
        m = LESSON_RE.match(path.name)
        if not m or path.suffix != ".html":
            # файлы трека без сквозного номера (программа курса, README и т.п.)
            if path.suffix in (".md", ".html") and path.is_file():
                track["files"].append({
                    "name": path.name,
                    "title": _md_title(path) if path.suffix == ".md"
                             else parse_lesson_html(_read(path))["title"] or path.stem,
                    "file": _rel(path, root),
                    "url": _url(_rel(path, root)),
                })
            continue  # уроки только со сквозным номером
        number = m.group(1)
        info = parse_lesson_html(_read(path))
        rel = _rel(path, root)
        seed = seeds.get(number, {})
        track["lessons"].append({
            "id": f"{track['id']}-{number}",
            "number": number,
            "track": track["id"],
            "track_title": track["title"],
            "title": info["title"] or path.stem,
            "page_title": info["page_title"],
            "kicker": info["kicker"],
            "summary": info["summary"],
            "interactive": info["interactive"],
            "file": rel,
            "url": _url(rel),
            "seed_status": seed.get("status", "planned"),
            "seed_label": seed.get("label", ""),
        })


def _scan_express_course(root: Path, course_dir: Path) -> dict:
    """Один экспресс-курс: подпапка внутри ветки «экспресс-курсы».

    id курса = имя папки, id урока = <курс>-<номер> (например
    «вайб-кодер-junior-0001»). index.html — вход в курс; если рядом лежит
    локальный глоссарий (*.html с «glossary» в имени), он прилагается к курсу.
    """
    course = {"id": course_dir.name, "title": course_dir.name,
              "kicker": "", "description": "", "lessons": [],
              "intro_url": None, "glossary_url": None}
    for path in sorted(course_dir.iterdir()):
        m = LESSON_RE.match(path.name)
        if m and path.suffix == ".html":
            number = m.group(1)
            info = parse_lesson_html(_read(path))
            rel = _rel(path, root)
            course["lessons"].append({
                "id": f"{course['id']}-{number}",
                "number": number,
                "track": course["id"],
                "track_title": course["title"],
                "title": info["title"] or path.stem,
                "page_title": info["page_title"],
                "kicker": info["kicker"],
                "summary": info["summary"],
                "interactive": info["interactive"],
                "file": rel,
                "url": _url(rel),
                "seed_status": "planned",
                "seed_label": "",
            })
        elif path.name == "index.html":
            info = parse_lesson_html(_read(path))
            course["title"] = info["title"] or course["title"]
            course["kicker"] = info["kicker"]
            course["description"] = info["summary"]
            course["intro_url"] = _url(_rel(path, root))
        elif "glossary" in path.name and path.suffix == ".html":
            course["glossary_url"] = _url(_rel(path, root))
    course["lessons"].sort(key=lambda l: l["number"])
    # index.html читается позже уроков (сортировка по имени) — обновляем заголовки
    for lesson in course["lessons"]:
        lesson["track_title"] = course["title"]
    return course


def _scan_express_courses(root: Path) -> list:
    """Ветка экспресс-курсов: каждая подпапка «экспресс-курсы/» — отдельный курс.

    Новая подпапка становится новым курсом без правки кода. Порядок — по имени
    папки (junior → middle → senior идут по алфавиту).
    """
    branch = root / EXPRESS_DIR
    if not branch.is_dir():
        return []
    courses = [_scan_express_course(root, d) for d in sorted(branch.iterdir())
               if d.is_dir()]
    return [c for c in courses if c["lessons"] or c["intro_url"]]


def _scan_references(root: Path) -> list:
    refs = []
    gloss_dir = root / "справочники"
    if gloss_dir.is_dir():
        for path in sorted(gloss_dir.glob("*.html")):
            stem = path.stem
            rel = _rel(path, root)
            refs.append({"id": stem,
                         "title": parse_lesson_html(_read(path))["title"] or stem,
                         "description": REF_DESCRIPTIONS.get(stem, ""),
                         "file": rel, "url": _url(rel)})
    return refs


def _scan_materials(root: Path) -> list:
    items = []
    mat_dir = root / "материалы"
    if mat_dir.is_dir():
        for path in sorted(p for p in mat_dir.iterdir() if p.is_file()):
            rel = _rel(path, root)
            items.append({"id": path.stem, "name": path.name,
                          "file": rel, "url": _url(rel),
                          "size_bytes": path.stat().st_size})
    return items


def _md_title(path: Path) -> str:
    for line in _read(path).splitlines():
        if line.startswith("# "):
            return _tag_text(line[2:])
    return path.stem


def _scan_documents(root: Path) -> tuple:
    docs, notes = [], []
    doc_dir = root / "документы-курса"
    if not doc_dir.is_dir():
        return docs, notes
    for path in sorted(doc_dir.glob("*.md")):
        rel = _rel(path, root)
        docs.append({"id": path.stem, "title": _md_title(path),
                     "file": rel, "url": _url(rel)})
    notes_dir = doc_dir / "записи-прогресса"
    if notes_dir.is_dir():
        note_re = re.compile(r"^(\d{4})-")
        for path in sorted(notes_dir.glob("*.md")):
            m = note_re.match(path.name)
            rel = _rel(path, root)
            notes.append({"id": path.stem,
                          "number": m.group(1) if m else "",
                          "title": _md_title(path),
                          "file": rel, "url": _url(rel)})
    return docs, notes


# ---------------------------------------------------------------- каталог API

def scan_catalog(root: Path) -> dict:
    """Полный каталог папки «обучение». Вызывается на каждый запрос — всегда свежий."""
    root = Path(root)
    seeds = parse_status_seeds(root)

    tracks = []
    lessons_dir = root / "уроки"
    if lessons_dir.is_dir():
        folders = sorted(p.name for p in lessons_dir.iterdir() if p.is_dir())
        # известные треки в фиксированном порядке: база → А → Б, дальше новые
        folders.sort(key=lambda f: list(KNOWN_TRACKS).index(f)
                     if f in KNOWN_TRACKS else len(KNOWN_TRACKS))
        for folder in folders:
            track = _make_track(folder)
            _collect_track_lessons(root, track, seeds)
            if track["lessons"] or folder in KNOWN_TRACKS:
                tracks.append(track)

    express_courses = _scan_express_courses(root)
    references = _scan_references(root)
    materials = _scan_materials(root)
    documents, progress_notes = _scan_documents(root)
    game_dev = _scan_game_dev(root)

    track_lessons = sum(len(t["lessons"]) for t in tracks)
    return {
        "api": "vibec",
        "version": 3,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "content_root": str(root),
        "tracks": tracks,
        "express_courses": express_courses,
        "game_dev": game_dev,
        "references": references,
        "materials": materials,
        "documents": documents,
        "progress_notes": progress_notes,
        "counts": {
            "tracks": len(tracks),
            "lessons": track_lessons,
            "express_courses": len(express_courses),
            "express_lessons": sum(len(c["lessons"]) for c in express_courses),
            "game_dev": 1 if game_dev else 0,
            "references": len(references),
            "materials": len(materials),
            "documents": len(documents),
            "progress_notes": len(progress_notes),
        },
    }


def all_lessons(catalog: dict) -> list:
    """Все уроки одним списком: треки, затем экспресс-курсы по порядку папок."""
    lessons = []
    for track in catalog["tracks"]:
        lessons.extend(track["lessons"])
    for course in catalog["express_courses"]:
        lessons.extend(course["lessons"])
    return lessons


def find_lesson(catalog: dict, lesson_id: str) -> dict | None:
    """Урок по id + соседи для навигения prev/next по общему порядку."""
    lessons = all_lessons(catalog)
    for i, lesson in enumerate(lessons):
        if lesson["id"] == lesson_id:
            result = dict(lesson)
            result["prev_id"] = lessons[i - 1]["id"] if i > 0 else None
            result["next_id"] = lessons[i + 1]["id"] if i + 1 < len(lessons) else None
            return result
    return None


def search_lessons(root: Path, catalog: dict, query: str, limit: int = 30) -> list:
    """Полнотекстовый поиск по HTML уроков (треки + экспресс). Регистр не важен."""
    needle = query.strip().casefold()
    if not needle:
        return []
    results = []
    for lesson in all_lessons(catalog):
        path = Path(root) / lesson["file"]
        if not path.is_file():
            continue
        text = plain_text(_read(path))
        pos = text.casefold().find(needle)
        if pos < 0:
            continue
        start = max(0, pos - 60)
        snippet = ("…" if start else "") + text[start:pos + 90].strip() + "…"
        results.append({"id": lesson["id"], "title": lesson["title"],
                        "track_title": lesson["track_title"],
                        "url": lesson["url"], "snippet": snippet})
        if len(results) >= limit:
            break
    return results
