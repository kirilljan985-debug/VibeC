"use strict";

// Проверка отображения документов: node front/markdown.test.cjs
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const window = { markdownit: require("./vendor/markdown-it.min.js") };
vm.runInNewContext(fs.readFileSync(path.join(__dirname, "markdown.js"), "utf8"), { window, URL });
const render = source => window.VibeCMarkdown.render(source, { baseURL: "http://localhost/content/документы/план.md" });

let result = render("# План\n\n## Шаг\n\n## Шаг\n\n### Детали\n\n**Смысл** и `код`.\n\n| Этап | Статус |\n|---|---|\n| 1 | готов |\n\n1. Первый\n2. Второй\n   - Вложенный\n\n> Цитата\n\n```python\nprint('<hello>')\n```\n");
assert.equal(result.headings.length, 4);
assert.equal(new Set(result.headings.map(item => item.id)).size, 4, "Повторные заголовки получают разные якоря");
assert.match(result.html, /<th scope="col">Этап<\/th>/);
assert.match(result.html, /<ol>/);
assert.match(result.html, /<ul>/);
assert.match(result.html, /<blockquote>/);
assert.match(result.html, /<strong>Смысл<\/strong>/);
assert.match(result.html, /<code>код<\/code>/);
assert.match(result.html, /&lt;hello&gt;/, "Примеры кода отображаются текстом");

result = render("# Журнал\n\n- [ ] Читать\n  - Вложенное пояснение\n- [x] Прочитано\n\n| Шаг | Отметка |\n|---|---|\n| Один | [ ] |\n");
assert.match(result.html, /aria-label="Не выполнено"/);
assert.match(result.html, /aria-label="Выполнено"/);
assert.doesNotMatch(result.html, /<input/, "Отметки документа нельзя случайно изменить");
assert.match(result.html, /Вложенное пояснение/);
assert.match(result.html, /<td>\[ \]<\/td>/, "Текст внутри таблицы сохраняется");

result = render('<script>alert(1)</script>\n\n<img src=x onerror="alert(1)">\n\n[Плохая ссылка](javascript:alert(1))\n\n[Локальный файл](file:///secret)\n\n![Изображение](https://example.com/tracker.png)\n');
assert.doesNotMatch(result.html, /<script|<img|href="(?:javascript|file):/i);
assert.match(result.html, /&lt;script&gt;/, "HTML показывается текстом");
assert.match(result.html, /rel="noopener noreferrer"/);

result = render("# Заголовок\n\n## Раздел\n\n[На раздел](#раздел)\n\n[Другой документ](../правила.md)\n");
assert.match(result.html, /data-document-anchor="document-section-раздел"/);
assert.match(result.html, /href="http:\/\/localhost\/content\/%D0%BF%D1%80%D0%B0%D0%B2%D0%B8%D0%BB%D0%B0.md"/);
assert.ok(render("").readingMinutes >= 1);
console.log("Проверки Markdown пройдены: структура, таблицы, вложенные списки, код, отметки, ссылки и безопасное отображение.");
