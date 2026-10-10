# -*- coding: utf-8 -*-
"""VibeC — HTTP-сервер портала курса.

Маршруты (контракт см. ИНТЕРФЕЙС.md):
  GET  /                    фронт (front/index.html) или страница-заглушка
  GET  /<файл>              статика фронта из front/
  GET  /api/catalog         каталог папки «обучение» (скан на каждый запрос)
  GET  /api/lesson/<id>     урок + соседи prev/next
  GET  /api/search?q=...    полнотекстовый поиск по урокам
  GET  /api/progress        отметки пользователя
  POST /api/progress        поставить/снять отметку
  GET  /api/meta            статус сервера
  GET  /content/<путь>      статика папки «обучение» (зеркало 1:1)

Запуск: python server/app.py [--port N] [--root PATH] [--no-browser]
"""
import argparse
import json
import mimetypes
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, parse_qs, unquote

sys.path.insert(0, str(Path(__file__).resolve().parent))

import config
import scanner
from store import ProgressStore, ALLOWED_STATUS

SERVER_VERSION = "VibeC/1.0"
CONTRACT_VERSION = "1.0"

# текстовые типы всегда отдаём с utf-8
TEXT_TYPES = ("text/", "application/json", "application/javascript")


def _content_type(path: Path) -> str:
    guessed = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    if guessed.startswith(TEXT_TYPES):
        return f"{guessed}; charset=utf-8"
    return guessed


class VibeCServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, handler, content_root: Path,
                 front_dir: Path, store: ProgressStore):
        super().__init__(address, handler)
        self.content_root = Path(content_root)
        self.front_dir = Path(front_dir)
        self.store = store
        self.started_at = threading.Event()  # выставляется после bind


class VibeCRequestHandler(BaseHTTPRequestHandler):
    server_version = SERVER_VERSION

    # ------------------------------------------------------------- утилиты

    def log_message(self, fmt, *args):  # лог ASCII-безопасный: консоль Windows
        msg = fmt % args
        sys.stderr.write(f"{self.address_string()} [{self.log_date_time_string()}] "
                         f"{msg.encode('ascii', 'backslashreplace').decode('ascii')}\n")

    def _send(self, status: int, body: bytes, content_type: str,
              cache: str = "no-store") -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", cache)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, obj, status: int = 200) -> None:
        body = json.dumps(obj, ensure_ascii=False, indent=2).encode("utf-8")
        self._send(status, body, "application/json; charset=utf-8")

    def _send_file(self, path: Path) -> None:
        try:
            body = path.read_bytes()
        except OSError:
            self._send_json({"error": "файл не читается"}, 500)
            return
        self._send(200, body, _content_type(path), cache="no-cache")

    def _read_json_body(self) -> dict | None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
            data = json.loads(self.rfile.read(length) or b"{}")
            return data if isinstance(data, dict) else None
        except (ValueError, OSError):
            return None

    # ------------------------------------------------------------- маршруты

    def do_GET(self) -> None:
        self._route(head=False)

    def do_HEAD(self) -> None:
        self._route(head=True)

    def _route(self, head: bool) -> None:
        parts = urlsplit(self.path)
        path = unquote(parts.path)
        if path.startswith("/api/"):
            self._api(path, parse_qs(parts.query), head)
        elif path == "/":
            self._front_index(head)
        elif path.startswith("/content/"):
            self._content(path[len("/content/"):], head)
        else:
            self._front_static(path, head)

    # ------------------------------------------------------------------ API

    def _api(self, path: str, query: dict, head: bool) -> None:
        if head:
            self._send(200, b"", "application/json; charset=utf-8")
            return
        if path == "/api/catalog":
            self._api_catalog()
        elif path.startswith("/api/lesson/"):
            self._api_lesson(unquote(path[len("/api/lesson/"):]))
        elif path == "/api/search":
            self._api_search(query)
        elif path == "/api/progress":
            self._api_progress_get()
        elif path == "/api/meta":
            self._api_meta()
        else:
            self._send_json({"error": "нет такого эндпоинта",
                             "hint": "см. ИНТЕРФЕЙС.md"}, 404)

    def _api_catalog(self) -> None:
        try:
            self._send_json(scanner.scan_catalog(self.server.content_root))
        except OSError as exc:
            self._send_json({"error": f"папка обучения недоступна: {exc}"}, 500)

    def _api_lesson(self, lesson_id: str) -> None:
        catalog = scanner.scan_catalog(self.server.content_root)
        lesson = scanner.find_lesson(catalog, lesson_id)
        if lesson is None:
            self._send_json({"error": f"урок {lesson_id!r} не найден"}, 404)
            return
        lesson["progress"] = self.server.store.all().get(lesson_id)
        self._send_json(lesson)

    def _api_search(self, query: dict) -> None:
        q = (query.get("q") or [""])[0]
        results = scanner.search_lessons(self.server.content_root,
                                         scanner.scan_catalog(self.server.content_root),
                                         q)
        self._send_json({"query": q, "count": len(results), "results": results})

    def _api_progress_get(self) -> None:
        self._send_json({"items": self.server.store.all()})

    def _api_meta(self) -> None:
        root = self.server.content_root
        catalog = scanner.scan_catalog(root) if root.is_dir() else None
        self._send_json({
            "name": "VibeC", "server": SERVER_VERSION,
            "contract": f"ИНТЕРФЕЙС.md v{CONTRACT_VERSION}",
            "content_root": str(root),
            "content_root_exists": root.is_dir(),
            "front_present": (self.server.front_dir / "index.html").is_file(),
            "counts": catalog["counts"] if catalog else None,
        })

    def do_POST(self) -> None:
        parts = urlsplit(self.path)
        if unquote(parts.path) != "/api/progress":
            self._send_json({"error": "POST поддерживается только на /api/progress"}, 404)
            return
        data = self._read_json_body()
        if data is None:
            self._send_json({"error": "тело запроса — не корректный JSON-объект"}, 400)
            return
        lesson_id = str(data.get("lesson_id", ""))
        if not lesson_id:
            self._send_json({"error": "обязательно поле lesson_id"}, 400)
            return
        status = data.get("status")
        if status is None:  # снять отметку
            removed = self.server.store.clear(lesson_id)
            self._send_json({"lesson_id": lesson_id, "cleared": removed,
                             "items": self.server.store.all()})
            return
        note = data.get("note")
        try:
            entry = self.server.store.set(lesson_id, str(status),
                                          str(note) if note else None)
        except ValueError as exc:
            self._send_json({"error": str(exc), "allowed": sorted(ALLOWED_STATUS)}, 400)
            return
        self._send_json({"lesson_id": lesson_id, "progress": entry,
                         "items": self.server.store.all()})

    # -------------------------------------------------------------- статика

    def _front_index(self, head: bool) -> None:
        index = self.server.front_dir / "index.html"
        if index.is_file():
            self._send_file(index)
            return
        body = PLACEHOLDER_HTML.encode("utf-8")
        if head:
            self._send(200, b"", "text/html; charset=utf-8")
            return
        self._send(200, body, "text/html; charset=utf-8")

    def _front_static(self, path: str, head: bool) -> None:
        # прочие пути — файлы фронта (app.js, style.css, ...), без выхода из front/
        front = self.server.front_dir.resolve()
        target = (front / path.lstrip("/")).resolve()
        if str(target).startswith(str(front)) and target.is_file() \
                and not target.name.startswith("."):
            self._send_file(target)
        else:
            self._send_json({"error": "не найдено", "path": path}, 404)

    def _content(self, rel: str, head: bool) -> None:
        root = self.server.content_root.resolve()
        target = (root / rel).resolve()
        inside = str(target).startswith(str(root))
        hidden = any(part.startswith(".") for part in target.relative_to(root).parts) \
            if inside else True
        if not (inside and not hidden and target.is_file()):
            self._send_json({"error": "нет доступа или файл не найден",
                             "path": rel}, 404)
            return
        if head:
            self._send(200, b"", _content_type(target))
            return
        self._send_file(target)


# ------------------------------------------------- страница-заглушка до фронта

PLACEHOLDER_HTML = """<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>VibeC · сервер работает, фронт ещё не приехал</title>
<style>
  :root { --bg:#14161c; --panel:#1d2029; --line:#2c3040; --text:#e8eaf2;
          --muted:#9aa0b5; --accent:#7c9cff; --ok:#5ad191; --warn:#e8b45a; }
  * { box-sizing:border-box; }
  body { margin:0; background:var(--bg); color:var(--text);
         font:16px/1.6 "Segoe UI", system-ui, sans-serif; }
  .wrap { max-width:880px; margin:0 auto; padding:40px 24px 80px; }
  h1 { font-size:28px; margin:0 0 4px; }
  .sub { color:var(--muted); margin-bottom:28px; }
  .badge { display:inline-block; padding:2px 10px; border-radius:12px;
           font-size:13px; background:#22303c; color:var(--ok); }
  .grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(120px,1fr));
          gap:12px; margin:20px 0 32px; }
  .cell { background:var(--panel); border:1px solid var(--line);
          border-radius:10px; padding:14px; }
  .num { font-size:24px; font-weight:700; color:var(--accent); }
  .lbl { color:var(--muted); font-size:13px; }
  h2 { font-size:18px; margin:32px 0 10px; }
  ul { padding-left:20px; }
  a { color:var(--accent); text-decoration:none; }
  a:hover { text-decoration:underline; }
  table { width:100%; border-collapse:collapse; background:var(--panel);
          border:1px solid var(--line); border-radius:10px; overflow:hidden; }
  td, th { padding:8px 12px; text-align:left; border-bottom:1px solid var(--line);
           font-size:14px; }
  code { background:#262a38; padding:1px 6px; border-radius:5px;
         font-size:13px; color:#c3cbf0; }
  .warn { color:var(--warn); }
  .note { color:var(--muted); font-size:14px; margin-top:28px;
          border-left:3px solid var(--line); padding-left:12px; }
</style>
</head>
<body>
<div class="wrap">
  <h1>VibeC <span class="badge">сервер работает</span></h1>
  <div class="sub">Бэкенд портала курса поднят и читает живую папку «обучение».
  Фронт ещё не добавлен — как только в <code>front/</code> появится
  <code>index.html</code>, он откроется здесь автоматически.</div>

  <h2>Что сейчас в папке обучения</h2>
  <div class="grid" id="counts"><span class="lbl">загружаю…</span></div>

  <h2>Разделы</h2>
  <ul id="tracks"><li>загружаю…</li></ul>

  <h2>API для фронта (контракт <span id="contract">v1.0</span>)</h2>
  <table>
    <tr><th>Эндпоинт</th><th>Что отдаёт</th></tr>
    <tr><td><code>GET /api/catalog</code></td><td>весь каталог: треки, уроки, экспресс-курс, справочники, документы</td></tr>
    <tr><td><code>GET /api/lesson/&lt;id&gt;</code></td><td>урок + соседи prev/next + его отметка прогресса</td></tr>
    <tr><td><code>GET /api/search?q=…</code></td><td>полнотекстовый поиск по урокам, со сниппетами</td></tr>
    <tr><td><code>GET /api/progress</code></td><td>отметки прогресса (персистентные)</td></tr>
    <tr><td><code>POST /api/progress</code></td><td><code>{"lesson_id":"base-0001","status":"done"}</code> — поставить; <code>{"lesson_id":"…","status":null}</code> — снять</td></tr>
    <tr><td><code>GET /api/meta</code></td><td>статус сервера и счётчики</td></tr>
    <tr><td><code>GET /content/&lt;путь&gt;</code></td><td>зеркало папки «обучение» — уроки открываются в iframe со всеми квизами</td></tr>
  </table>

  <div class="note">Проверка руками: открой любой урок по ссылке выше — квизы и стили
  работают, потому что бэкенд раздаёт папку «обучение» как есть. Полный контракт —
  в файле <code>ИНТЕРФЕЙС.md</code> репозитория VibeC.</div>
</div>
<script>
async function main() {
  try {
    const [meta, catalog] = await Promise.all([
      fetch("/api/meta").then(r => r.json()),
      fetch("/api/catalog").then(r => r.json()),
    ]);
    document.getElementById("contract").textContent =
      (meta.contract || "").replace("ИНТЕРФЕЙС.md ", "") || "v1.0";
    const c = catalog.counts || {};
    const cells = [["треки", c.tracks], ["уроки", c.lessons],
      ["экспресс-уроки", c.express_lessons], ["термины-справочники", c.references],
      ["документы", c.documents], ["записи прогресса", c.progress_notes]];
    document.getElementById("counts").innerHTML = cells.map(([lbl, n]) =>
      `<div class="cell"><div class="num">${n ?? "—"}</div><div class="lbl">${lbl}</div></div>`).join("");
    document.getElementById("tracks").innerHTML = catalog.tracks.map(t => {
      const first = t.lessons[0];
      return `<li><strong>${t.title}</strong> — уроков: ${t.lessons.length}` +
        (first ? ` · <a href="${first.url}">открыть первый: ${first.title}</a>` : ``) +
        `</li>`;
    }).join("") +
    `<li><strong>${catalog.express_course.title}</strong> — уроков: ${catalog.express_course.lessons.length}` +
    (catalog.express_course.intro_url ? ` · <a href="${catalog.express_course.intro_url}">вход в курс</a>` : ``) + `</li>`;
  } catch (e) {
    document.getElementById("counts").innerHTML =
      `<span class="warn">API недоступно: ${e}</span>`;
  }
}
main();
</script>
</body>
</html>
"""


# --------------------------------------------------------------------- запуск

def create_server(host: str, port: int, content_root: Path,
                  front_dir: Path, progress_file: Path) -> VibeCServer:
    store = ProgressStore(progress_file)
    return VibeCServer((host, port), VibeCRequestHandler,
                       content_root, front_dir, store)


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description="VibeC — сервер портала курса")
    parser.add_argument("--host", default=config.HOST)
    parser.add_argument("--port", type=int, default=config.PORT)
    parser.add_argument("--root", type=Path, default=None,
                        help="путь к папке «обучение» (иначе VIBEC_CONTENT_ROOT)")
    parser.add_argument("--no-browser", action="store_true",
                        help="не открывать браузер при старте")
    args = parser.parse_args(argv)

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

    content_root = args.root or config.content_root()
    server = create_server(args.host, args.port, content_root,
                           config.FRONT_DIR, config.PROGRESS_FILE)

    url = f"http://{args.host}:{args.port}/"
    print(f"VibeC {SERVER_VERSION} · контракт ИНТЕРФЕЙС.md v{CONTRACT_VERSION}")
    print(f"Папка обучения : {content_root}"
          + ("" if content_root.is_dir() else "  [НЕ НАЙДЕНА — каталог будет пуст!]"))
    print(f"Адрес          : {url}")
    print("Остановка      : Ctrl+C")

    if config.OPEN_BROWSER and not args.no_browser:
        threading.Timer(0.8, webbrowser.open, args=(url,)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nСервер остановлен.")
        server.server_close()


if __name__ == "__main__":
    main()
