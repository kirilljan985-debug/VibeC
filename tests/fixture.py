# -*- coding: utf-8 -*-
"""Фикстура: миниатюра папки «обучение» для тестов (создаётся во временной папке)."""
from pathlib import Path

EXPRESS_DIRNAME = "экспресс-курс-вайб-кодера"

MEMORY_MD = """# 🧠 ПАМЯТЬ КУРСА

## 📊 Статус (тест)

| Что | Статус |
|---|---|
| 0001 «Как запускается программа» | ✅ пройден |
| 0003 (Трек А: глоссарий) | ✅ пройден, боевое задание выполнено |
| 0005 (Трек Б: переменные в деле) | 📖 выдан: учим переменные |
| 0007 (Трек Б: условия) | ⏳ следующий |
| Stepik Модуль 1 | ❓ стартовать |
"""

LESSON_TEMPLATE = """<!DOCTYPE html>
<html lang="ru">
<head><meta charset="UTF-8"><title>{page_title}</title>
<link rel="stylesheet" href="../../компоненты/style.css"></head>
<body>
<div class="lesson-kicker">{kicker}</div>
<h1>{title}</h1>
<p class="lesson-meta">{summary}</p>
<p>Текст урока про {keyword} и ещё немного слов.</p>
<script src="../../компоненты/quiz.js"></script>
</body></html>
"""


def lesson_html(page_title, kicker, title, summary, keyword,
                extra_scripts=()) -> str:
    scripts = "".join(f'<script src="../../компоненты/{s}"></script>'
                      for s in extra_scripts)
    return LESSON_TEMPLATE.format(page_title=page_title, kicker=kicker,
                                  title=title, summary=summary, keyword=keyword,
                                  ) + scripts


def build_fixture(root: Path) -> Path:
    """Собирает структуру, повторяющую реальную папку «обучение» в миниатюре."""
    root = Path(root)
    (root / "компоненты").mkdir(parents=True)
    (root / "компоненты" / "style.css").write_text("body{}", encoding="utf-8")
    (root / "компоненты" / "quiz.js").write_text("//q", encoding="utf-8")
    (root / "компоненты" / "flashcards.js").write_text("//f", encoding="utf-8")

    lessons = root / "уроки"
    base = lessons / "база"
    base.mkdir(parents=True)
    (base / "0001-kak-zapuskaetsya-programma.html").write_text(
        lesson_html("Урок 0001 · База · Запуск",
                    "Урок 0001 · База · ~20 минут",
                    "Как запускается программа",
                    "Первый урок: что происходит при запуске.",
                    "запуске"), encoding="utf-8")
    (base / "0002-terminal.html").write_text(
        lesson_html("Урок 0002 · База · Терминал",
                    "Урок 0002 · База · ~20 минут",
                    "Терминал — главный инструмент",
                    "Второй урок: командная строка.",
                    "терминале"), encoding="utf-8")

    track_a = lessons / "трек-А-ии-инженерия"
    track_a.mkdir(parents=True)
    (track_a / "0003-glossary.html").write_text(
        lesson_html("Урок 0003 · Трек А · Глоссарий",
                    "Урок 0003 · Трек А · ~15 минут",
                    "Глоссарий вайб-кодера",
                    "Учим термины.",
                    "глоссарии",
                    extra_scripts=("flashcards.js",)), encoding="utf-8")

    track_b = lessons / "трек-Б-питон"
    track_b.mkdir(parents=True)
    (track_b / "0005-peremennye.html").write_text(
        lesson_html("Урок 0005 · Трек Б · Переменные",
                    "Урок 0005 · Трек Б · Python · ~15 минут",
                    "Переменные в деле",
                    "Первый урок трека Б.",
                    "переменных"), encoding="utf-8")
    (track_b / "README.md").write_text("# Список уроков Б\n", encoding="utf-8")

    # неизвестный трек — должен подхватиться автоматически
    track_v = lessons / "трек-В-новый"
    track_v.mkdir(parents=True)
    (track_v / "0100-novyy.html").write_text(
        lesson_html("Урок 0100 · Трек В",
                    "Урок 0100 · Трек В",
                    "Новый трек",
                    "Урок из новой папки.",
                    "новинке"), encoding="utf-8")

    express = root / EXPRESS_DIRNAME
    express.mkdir(parents=True)
    (express / "index.html").write_text(
        "<html><head><meta charset='UTF-8'><title>Экспресс-курс вайб-кодера"
        " · работа с ИИ-агентом</title></head><body><h1>Вайб-кодер</h1></body></html>",
        encoding="utf-8")
    (express / "0001-roli-vayb-kodera.html").write_text(
        lesson_html("Экспресс 0001 · Роли",
                    "Экспресс-курс · Урок 1",
                    "Роль вайб-кодера",
                    "Кто такой вайб-кодер.",
                    "роли"), encoding="utf-8")
    (express / "glossary-interactive.html").write_text(
        "<html><head><meta charset='UTF-8'><title>Глоссарий экспресс-курса"
        "</title></head><body></body></html>", encoding="utf-8")

    refs = root / "справочники"
    refs.mkdir(parents=True)
    (refs / "glossary-core.html").write_text(
        "<html><head><meta charset='UTF-8'><title>Ядерный глоссарий курса"
        "</title></head><body></body></html>", encoding="utf-8")
    (refs / "python-minimum.html").write_text(
        "<html><head><meta charset='UTF-8'><title>Python-минимум</title></head>"
        "<body></body></html>", encoding="utf-8")

    mats = root / "материалы"
    mats.mkdir(parents=True)
    (mats / "progit-ru.pdf").write_bytes(b"%PDF-1.4 fake")

    docs = root / "документы-курса"
    docs.mkdir(parents=True)
    (docs / "МИССИЯ.md").write_text("# 🎯 Миссия\nСтать вайб-кодером.\n",
                                    encoding="utf-8")
    notes = docs / "записи-прогресса"
    notes.mkdir(parents=True)
    (notes / "0001-стартовый-уровень.md").write_text(
        "# Запись 0001 · Стартовый уровень\nЗафиксировали старт.\n",
        encoding="utf-8")

    (root / "ПАМЯТЬ.md").write_text(MEMORY_MD, encoding="utf-8")

    # посторонние проекты в корне обучения — сканер обязан их игнорировать
    (root / "rpg-adventure").mkdir()
    (root / "rpg-adventure" / "project.godot").write_text("config", encoding="utf-8")
    (root / "python-lab").mkdir()
    (root / "python-lab" / "game.py").write_text("print('hi')", encoding="utf-8")
    return root
