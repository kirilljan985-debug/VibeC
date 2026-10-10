"use strict";

(() => {
  const $ = (selector) => document.querySelector(selector);
  const content = $("#content");
  const state = { catalog: null, progress: {}, filter: "all", pending: new Set(), openTracks: new Set(), resource: null };
  const statusLabels = { done: "Пройдено", reading: "Читаю", "in-progress": "В процессе", next: "Следующий", planned: "Не начат", "not-started": "Не начат" };
  let routeVersion = 0, catalogVersion = 0, progressRevision = 0, searchTimer, searchController, toastTimer;
  let catalogController;

  const esc = (value = "") => String(value ?? "").replace(/[&<>"']/g, char => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char]);
  const seedTip = lesson => !state.progress[lesson.id]?.status && lesson.seed_label ? `Заметка преподавателя: ${lesson.seed_label}` : "";
  const effectiveStatus = lesson => state.progress[lesson.id]?.status || lesson.seed_status || "planned";
  const allLessons = () => [...(state.catalog?.tracks || []).flatMap(track => track.lessons || []), ...(state.catalog?.express_courses || []).flatMap(course => course.lessons || [])];
  const completed = lessons => lessons.filter(lesson => effectiveStatus(lesson) === "done").length;
  const percent = lessons => lessons.length ? Math.round(completed(lessons) / lessons.length * 100) : 0;
  const lessonHref = id => `#lesson/${encodeURIComponent(id)}`;
  const filtered = lessons => lessons.filter(lesson => state.filter === "all" || (state.filter === "done" ? effectiveStatus(lesson) === "done" : effectiveStatus(lesson) !== "done"));
  const resourceGroups = () => [
    ["references", "Справочники", "◫", state.catalog?.references || []],
    ["materials", "Материалы", "↓", state.catalog?.materials || []],
    ["documents", "Документы курса", "▧", state.catalog?.documents || []],
    ["progress_notes", "Записи прогресса", "◷", state.catalog?.progress_notes || []],
  ];
  function safeURL(url) {
    if (typeof url !== "string" || !url.startsWith("/content/") || url.includes("\\")) return "";
    const parsed = new URL(url, location.origin);
    return parsed.origin === location.origin && parsed.pathname.startsWith("/content/") ? parsed.href : "";
  }
  async function request(url, options = {}) {
    const controller = new AbortController();
    const abort = () => controller.abort();
    if (options.signal?.aborted) controller.abort();
    options.signal?.addEventListener("abort", abort, { once: true });
    let timedOut = false;
    const timeout = setTimeout(() => { timedOut = true; controller.abort(); }, 15000);
    try {
      const response = await fetch(url, { cache: "no-store", ...options, signal: controller.signal });
      if (options.raw) {
        if (!response.ok) throw new Error(`Ошибка сервера (${response.status}).`);
        return await response.text();
      }
      let data;
      try { data = await response.json(); } catch { throw new Error("Сервер вернул ответ, который не удалось прочитать."); }
      if (!response.ok) throw new Error(data.error || `Ошибка сервера (${response.status}).`);
      return data;
    } catch (error) {
      if (timedOut) throw new Error("Сервер долго не отвечает. Попробуйте ещё раз.");
      throw error;
    } finally {
      clearTimeout(timeout);
      options.signal?.removeEventListener("abort", abort);
    }
  }
  function toast(message) {
    const element = $("#toast");
    element.textContent = message;
    element.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { element.hidden = true; }, 4500);
  }
  function notice(message = "") {
    $("#notice").innerHTML = message ? `<div class="notice">${esc(message)} <button type="button" data-action="reload">Повторить</button></div>` : "";
  }
  function route() {
    const hash = location.hash.slice(1);
    const [page, ...parts] = hash.split("/");
    let id = "";
    try { id = decodeURIComponent(parts.join("/")); } catch { /* Invalid fragment shows a missing item. */ }
    return { page: page || "home", id };
  }
  function progressBar(lessons) {
    return `<div class="progress-bar" role="progressbar" aria-label="Пройденные уроки" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${percent(lessons)}"><span style="width:${percent(lessons)}%"></span></div>`;
  }
  function completionButton(lesson, full = false) {
    const done = effectiveStatus(lesson) === "done";
    const pending = state.pending.has(lesson.id);
    const label = done ? "Снять отметку «пройдено»" : "Отметить как пройденное";
    return `<button type="button" class="${full ? "button subtle" : `completion${done ? " checked" : ""}`}" data-action="complete" data-id="${esc(lesson.id)}" aria-label="${esc(`${label}: ${lesson.title}`)}" aria-pressed="${done}" ${pending ? 'aria-disabled="true"' : ""} title="${label}">${pending ? "…" : done ? "✓" : full ? "○" : ""}${full ? ` ${done ? "Пройдено" : "Отметить пройденным"}` : ""}</button>`;
  }
  function lessonRow(lesson) {
    const status = effectiveStatus(lesson);
    const badges = (lesson.interactive || []).map(type => ({ quiz: "Квиз", flashcards: "Карточки", glossary: "Глоссарий" })[type]).filter(Boolean);
    return `<div class="lesson-row"><a class="lesson-open" href="${lessonHref(lesson.id)}"><span class="lesson-number">${esc(lesson.number)}</span><span class="lesson-info"><span class="lesson-title">${esc(lesson.title)}</span>${lesson.kicker ? `<span class="lesson-kicker">${esc(lesson.kicker)}</span>` : ""}<span class="badges"><span class="badge status ${esc(status)}"${seedTip(lesson) ? ` title="${esc(seedTip(lesson))}"` : ""}>${esc(statusLabels[status] || "Не начат")}</span>${badges.map(label => `<span class="badge">${label}</span>`).join("")}</span></span></a>${completionButton(lesson)}</div>`;
  }
  function heading(title, subtitle, eyebrow = "ВАШЕ ПРОСТРАНСТВО") {
    return `<div class="page-heading"><div><div class="eyebrow">${eyebrow}</div><h1>${esc(title)}</h1><p>${esc(subtitle)}</p></div><span class="small-tag"><span class="live-dot"></span> В своём темпе</span></div>`;
  }
  function filters() {
    return `<div class="filter-tabs" role="group" aria-label="Фильтр уроков">${[["all", "Все уроки"], ["unfinished", "Не пройдены"], ["done", "Пройденные"]].map(([value, label]) => `<button type="button" data-action="filter" data-filter="${value}" aria-pressed="${state.filter === value}" class="${state.filter === value ? "active" : ""}">${label}</button>`).join("")}</div>`;
  }
  function renderTracks(expanded = false) {
    const tracks = state.catalog.tracks || [];
    if (!tracks.length) return `<div class="empty">Уроков пока нет. Когда они появятся в папке обучения, вы увидите их здесь.</div>`;
    return `<div class="track-grid">${tracks.map((track, index) => {
      const lessons = track.lessons || [], visible = filtered(lessons);
      const title = track.title || "Новый трек";
      const open = expanded || state.openTracks.has(track.id);
      return `<article class="track"><div class="track-symbol" aria-hidden="true">${["⌘", "✳", "&lt;/&gt;"][index % 3]}</div><h3>${esc(title)}</h3><p class="track-description">${esc(track.description || "Новый раздел вашего курса. Открывайте уроки и двигайтесь в своём темпе.")}</p><div class="progress-meta"><span>${completed(lessons)} из ${lessons.length} пройдено</span><span>${percent(lessons)}%</span></div>${progressBar(lessons)}<details data-track="${esc(track.id)}" ${open ? "open" : ""}><summary>Уроки трека · ${visible.length}</summary><div class="lesson-list">${visible.map(lessonRow).join("") || `<p class="empty">${lessons.length ? "Нет уроков с выбранным статусом." : "Уроки скоро появятся."}</p>`}</div></details></article>`;
    }).join("")}</div>`;
  }
  function expressCourseBlock(course, index, total) {
    const lessons = course.lessons || [];
    const intro = safeURL(course.intro_url), glossary = safeURL(course.glossary_url);
    const next = lessons.find(lesson => effectiveStatus(lesson) !== "done") || lessons[0];
    return `<div class="express-panel"><div><div class="eyebrow">КУРС ${index + 1} ИЗ ${total}</div><h3>${esc(course.title || course.id)}</h3>${course.kicker ? `<p class="express-kicker">${esc(course.kicker)}</p>` : ""}<p>${esc(course.description || "Курс ветки «Вайб-кодер».")}</p><div class="progress-meta"><span>${completed(lessons)} из ${lessons.length} пройдено</span><span>${percent(lessons)}%</span></div>${progressBar(lessons)}<div class="express-links">${intro ? `<a class="text-link" href="#resource/${encodeURIComponent(`express-intro:${course.id}`)}">О курсе ↗</a>` : ""}${glossary ? `<a class="text-link" href="#resource/${encodeURIComponent(`express-glossary:${course.id}`)}">Глоссарий ↗</a>` : ""}</div></div>${lessons.length ? `<a class="button primary" href="${lessonHref(next.id)}">${effectiveStatus(next) === "done" ? "Повторить курс" : "Открыть курс"} <span aria-hidden="true">→</span></a>` : ""}</div><div class="express-lessons">${filtered(lessons).map(lessonRow).join("") || `<div class="empty">${lessons.length ? "Нет уроков с выбранным статусом." : "В этом курсе пока нет уроков."}</div>`}</div>`;
  }
  function renderExpress() {
    const courses = state.catalog.express_courses || [];
    return courses.map((course, index) => expressCourseBlock(course, index, courses.length)).join("") || `<div class="empty">Экспресс-курсы появятся здесь, когда будут добавлены в папку обучения.</div>`;
  }
  function renderResources() {
    const groups = resourceGroups().filter(([, , , items]) => items.length);
    return groups.map(([group, title, symbol, items]) => `<h3 class="group-label">${title} · ${items.length}</h3><div class="resource-grid">${items.map(item => {
      const href = `#resource/${encodeURIComponent(`${group}:${item.file || item.id}`)}`;
      const size = item.size_bytes != null ? `${Math.max(1, Math.round(item.size_bytes / 1024))} КБ` : "";
      return `<a class="resource" href="${href}"><span class="resource-symbol" aria-hidden="true">${symbol}</span><span class="resource-body"><strong>${esc(item.title || item.name || item.id)}</strong><small>${esc(item.description || size || (group === "progress_notes" ? "Дневник обучения" : group === "documents" ? "Документ курса" : "Открыть материал"))}</small></span><span class="resource-arrow" aria-hidden="true">↗</span></a>`;
    }).join("")}</div>`).join("") || `<div class="empty">Справочники и документы появятся здесь, когда будут добавлены в курс.</div>`;
  }
  function renderDashboard(page) {
    if (page === "lessons") return heading("Уроки", "Каждый урок — ещё один шаг от идеи к работающему проекту.", "ОСНОВНОЙ КУРС") + filters() + renderTracks(true);
    if (page === "express") return heading("Экспресс-курсы", "Ветка «Вайб-кодер»: junior, middle, senior — проходите грейд за грейдом.", "БЫСТРЫЙ СТАРТ") + filters() + renderExpress();
    if (page === "resources") return heading("Всё под рукой", "Справочники, материалы курса и ваш дневник обучения.", "БИБЛИОТЕКА КУРСА") + renderResources();
    const lessons = allLessons(), done = completed(lessons);
    const resume = lessons.find(lesson => ["reading", "in-progress"].includes(effectiveStatus(lesson))) || lessons.find(lesson => effectiveStatus(lesson) !== "done");
    const heroTitle = resume?.title || (lessons.length ? "Все уроки пройдены. Отличная работа!" : "Ваш курс начинается здесь");
    const heroText = resume?.summary || (lessons.length ? "Можно вернуться к материалам, закрепить знания или дождаться новых уроков." : "Добавленные в папку обучения уроки и материалы появятся на этой странице.");
    const resources = resourceGroups().reduce((sum, [, , , items]) => sum + items.length, 0);
    return heading("Новый день. Новые навыки.", "Продолжайте с того места, где остановились. Всё нужное уже здесь.") +
      `<section class="hero" aria-label="Продолжить обучение"><div><div class="eyebrow">${resume ? "ПРОДОЛЖИТЬ ОБУЧЕНИЕ" : "ВАШ УЧЕБНЫЙ МАРШРУТ"}</div><h2>${esc(heroTitle)}</h2><p>${esc(heroText)}</p>${resume ? `<a class="button primary" href="${lessonHref(resume.id)}">${["reading", "in-progress"].includes(effectiveStatus(resume)) ? "Продолжить урок" : "Начать урок"} <span aria-hidden="true">→</span></a>` : `<a class="button primary" href="#lessons">К урокам <span aria-hidden="true">→</span></a>`}</div><div class="hero-side"><strong>${percent(lessons)}<span style="font-size:.55em">%</span></strong><span>курса пройдено</span>${progressBar(lessons)}<small>${done} из ${lessons.length} уроков</small></div></section>` +
      `<div class="stats">${[["▤", lessons.length, "Уроков в курсе"], ["✓", done, "Пройдено"], ["◈", (state.catalog.tracks || []).length, "Учебных треков"], ["◫", resources, "Материалов под рукой"]].map(([icon, value, label]) => `<div class="stat"><span class="stat-icon" aria-hidden="true">${icon}</span><div><strong>${value}</strong><small>${label}</small></div></div>`).join("")}</div>` +
      `<section class="section"><div class="section-head"><div><h2><span class="section-number">01</span>Ваши учебные треки</h2><p>Выбирайте направление и двигайтесь шаг за шагом</p></div><a class="text-link" href="#lessons">Все уроки →</a></div>${filters()}${renderTracks()}</section>` +
      `<section class="section"><div class="section-head"><h2><span class="section-number">02</span>Экспресс-курсы</h2><a class="text-link" href="#express">К курсу →</a></div>${renderExpress()}</section>` +
      `<section class="section"><div class="section-head"><h2><span class="section-number">03</span>Справочники и документы</h2><a class="text-link" href="#resources">Открыть всё →</a></div>${renderResources()}</section>`;
  }
  function viewerHTML(item, lesson = false) {
    const url = safeURL(item.url);
    if (!url) throw new Error("У материала нет доступной ссылки.");
    const markdown = /\.md$/i.test(new URL(url).pathname);
    const isExpress = lesson && (state.catalog?.express_courses || []).some(course => course.id === item.track);
    return `<div class="viewer-toolbar"><a class="button subtle" href="#${lesson ? (isExpress ? "express" : "lessons") : "resources"}">← ${lesson ? (isExpress ? "К экспресс-курсам" : "К урокам") : "К материалам"}</a>${lesson ? completionButton(item, true) : ""}<a class="button subtle" href="${esc(url)}" target="_blank" rel="noopener">Открыть отдельно ↗</a></div><div class="viewer-heading"><div class="eyebrow">${esc(item.track_title || "МАТЕРИАЛ КУРСА")}</div><h1>${esc(item.title || item.name)}</h1>${item.kicker ? `<p>${esc(item.kicker)}</p>` : ""}${lesson && !item.progress?.status && item.seed_label ? `<p class="seed-note">Преподаватель: ${esc(item.seed_label)}</p>` : ""}</div>${markdown ? `<pre class="document-text" id="document-text">Загружаем документ…</pre>` : `<iframe class="viewer-frame" src="${esc(url)}" title="${esc(item.title || item.name)}"></iframe>`}${lesson ? `<div class="viewer-bottom">${item.prev_id ? `<a class="button subtle" href="${lessonHref(item.prev_id)}">← Предыдущий урок</a>` : "<span></span>"}${item.next_id ? `<a class="button subtle" href="${lessonHref(item.next_id)}">Следующий урок →</a>` : `<span class="small-tag">Последний урок курса</span>`}</div>` : ""}`;
  }
  function findResource(id) {
    // служебные страницы курса ветки «экспресс-курсы»: express-intro:<курс>, express-glossary:<курс>
    for (const kind of ["express-intro", "express-glossary"]) {
      if (id.startsWith(`${kind}:`)) {
        const courseId = id.slice(kind.length + 1);
        const course = (state.catalog?.express_courses || []).find(item => item.id === courseId);
        if (!course) return null;
        const url = kind === "express-intro" ? course.intro_url : course.glossary_url;
        const label = kind === "express-intro" ? "Знакомство с курсом" : "Глоссарий курса";
        return { title: `${label}: ${course.title}`, url };
      }
    }
    const separator = id.indexOf(":");
    const group = id.slice(0, separator), key = id.slice(separator + 1);
    return resourceGroups().find(([name]) => name === group)?.[3].find(item => (item.file || item.id) === key);
  }
  function setContent(html) {
    content.innerHTML = html;
    content.setAttribute("aria-busy", "false");
  }
  function errorContent(error) {
    return `<div class="empty"><h2>Не удалось открыть страницу</h2><p>${esc(error.message || "Проверьте, что сервер VibeC запущен.")}</p><button class="button primary" type="button" data-action="reload">Повторить</button> <a class="button subtle" href="#home">На главную</a></div>`;
  }
  async function renderRoute({ focus = false } = {}) {
    const version = ++routeVersion;
    searchController?.abort();
    const { page, id } = route();
    state.resource = null;
    const section = ["home", "lessons", "express", "resources"].includes(page) ? page : page === "resource" ? "resources" : page === "lesson" ? "lessons" : "";
    document.querySelectorAll("[data-nav]").forEach(link => {
      const active = link.dataset.nav === section;
      link.classList.toggle("active", active);
      if (active) link.setAttribute("aria-current", "page"); else link.removeAttribute("aria-current");
    });
    const pageName = ({ home: "Обзор", lessons: "Уроки", express: "Экспресс-курсы", resources: "Библиотека", lesson: "Урок", resource: "Материал", search: "Поиск" })[page] || "Страница";
    $("#breadcrumb").innerHTML = `Мой курс <span>/</span> ${pageName}`;
    document.title = `${pageName} · VibeC`;
    if (page === "search") $("#search").value = id;
    else $("#search").value = "";
    if (!state.catalog) return;
    if (focus) { window.scrollTo({ top: 0 }); $("#main").focus({ preventScroll: true }); }
    try {
      if (["home", "lessons", "express", "resources"].includes(page)) { setContent(renderDashboard(page)); return; }
      if (page === "lesson") {
        setContent(`<div class="loading"><span class="spinner"></span>Открываем урок…</div>`);
        content.setAttribute("aria-busy", "true");
        const item = await request(`/api/lesson/${encodeURIComponent(id)}`);
        if (version !== routeVersion) return;
        if (!state.pending.has(item.id)) {
          if (item.progress) state.progress[item.id] = item.progress;
          else delete state.progress[item.id];
        }
        state.resource = item;
        document.title = `${item.title} · VibeC`;
        setContent(viewerHTML(item, true));
        return;
      }
      if (page === "resource") {
        const item = findResource(id);
        if (!item) throw new Error("Материал не найден. Возможно, он был удалён из курса.");
        state.resource = item;
        setContent(viewerHTML(item));
        document.title = `${item.title || item.name} · VibeC`;
        if ($("#document-text")) {
          const text = await request(safeURL(item.url), { raw: true });
          if (version === routeVersion && $("#document-text")) $("#document-text").textContent = text;
        }
        return;
      }
      if (page === "search") { await search(id, version); return; }
      throw new Error("Такой страницы нет.");
    } catch (error) {
      if (version !== routeVersion || error.name === "AbortError") return;
      setContent(errorContent(error));
    }
  }
  function highlighted(text, query) {
    if (!query) return esc(text);
    const source = String(text), start = source.toLocaleLowerCase().indexOf(query.toLocaleLowerCase());
    if (start < 0) return esc(source);
    return esc(source.slice(0, start)) + `<mark>${esc(source.slice(start, start + query.length))}</mark>` + esc(source.slice(start + query.length));
  }
  async function search(query, version) {
    const term = query.trim();
    const title = heading("Поиск по курсу", term ? `Результаты по запросу «${term}»` : "Введите слово или тему в строке поиска.", "НАЙТИ И РАЗОБРАТЬСЯ");
    if (!term) { setContent(title + `<div class="empty">Ищем в содержимом всех уроков, включая экспресс-курс.</div>`); return; }
    searchController = new AbortController();
    setContent(title + `<div class="loading"><span class="spinner"></span>Ищем в уроках…</div>`);
    content.setAttribute("aria-busy", "true");
    const data = await request(`/api/search?q=${encodeURIComponent(term)}`, { signal: searchController.signal });
    if (version !== routeVersion) return;
    const results = data.results || [];
    setContent(title + (results.length ? `<p class="group-label">Найдено уроков: ${results.length}</p><div class="search-results">${results.map(item => `<article class="search-result"><small>${esc(item.track_title)}</small><h2><a class="text-link" href="${lessonHref(item.id)}">${esc(item.title)} →</a></h2><p>${highlighted(item.snippet, term)}</p></article>`).join("")}</div>` : `<div class="empty"><h3>Пока ничего не найдено</h3><p>Попробуйте другое слово или более короткий запрос.</p></div>`));
  }
  async function loadCatalog({ quiet = false } = {}) {
    const version = ++catalogVersion;
    const revision = progressRevision;
    catalogController?.abort();
    catalogController = new AbortController();
    const signal = catalogController.signal;
    $("#refresh").disabled = true;
    try {
      const catalog = await request("/api/catalog", { signal });
      if (!Array.isArray(catalog.tracks)) throw new Error("Каталог курса имеет неизвестный формат.");
      let progress, progressError;
      try { progress = await request("/api/progress", { signal }); } catch (error) { if (error.name === "AbortError") throw error; progressError = error; }
      if (version !== catalogVersion) return;
      const changed = !state.catalog || JSON.stringify({ ...catalog, generated_at: undefined }) !== JSON.stringify({ ...state.catalog, generated_at: undefined });
      const previousProgress = JSON.stringify(state.progress);
      state.catalog = catalog;
      if (progress && !state.pending.size && revision === progressRevision) state.progress = progress.items || {};
      $("#lesson-count").textContent = catalog.tracks.reduce((sum, track) => sum + (track.lessons || []).length, 0);
      $("#sync-label").textContent = `Обновлено ${new Intl.DateTimeFormat("ru-RU", { hour: "2-digit", minute: "2-digit" }).format(new Date())}`;
      notice(progressError ? "Каталог загружен, но сохранённые отметки прогресса сейчас недоступны." : "");
      const page = route().page;
      if (!quiet || ((changed || previousProgress !== JSON.stringify(state.progress)) && ["home", "lessons", "express", "resources"].includes(page))) await renderRoute();
      else if (quiet && (changed || previousProgress !== JSON.stringify(state.progress)) && page === "lesson" && state.resource) {
        // открытый урок: молча обновляем данные и кнопку отметки, не перерисовывая iframe
        const fresh = allLessons().find(item => item.id === state.resource.id);
        if (fresh) {
          Object.assign(state.resource, fresh);
          state.resource.progress = state.progress[fresh.id] || null;
          updateCompletionUI();
        } else {
          state.resource = null;
          setContent(`<div class="empty"><h2>Урок исчез из курса</h2><p>Похоже, преподаватель убрал или переработал этот урок.</p><a class="button primary" href="#home">На главную</a></div>`);
        }
      }
    } catch (error) {
      if (error.name === "AbortError" || version !== catalogVersion) return;
      if (state.catalog) notice("Не удалось обновить курс. Показаны последние загруженные данные.");
      else setContent(errorContent(new Error("Не удалось подключиться к серверу VibeC. Запустите «запуск.bat» и повторите загрузку.")));
    } finally { if (version === catalogVersion) $("#refresh").disabled = false; }
  }
  function updateCompletionUI() {
    const focusedButton = document.activeElement?.dataset.action === "complete" ? document.activeElement.dataset.id : null;
    const current = route();
    if (["home", "lessons", "express", "resources"].includes(current.page)) setContent(renderDashboard(current.page));
    else if (current.page === "lesson" && state.resource) {
      const button = content.querySelector('[data-action="complete"]');
      if (button) button.outerHTML = completionButton(state.resource, true);
    }
    if (focusedButton) {
      const replacement = [...content.querySelectorAll('[data-action="complete"]')].find(button => button.dataset.id === focusedButton);
      if (replacement && !replacement.disabled) replacement.focus({ preventScroll: true });
      else $("#main").focus({ preventScroll: true });
    }
  }
  async function toggleCompletion(id) {
    if (state.pending.has(id)) return;
    // отметка ставится только уроку из текущего каталога: урок мог исчезнуть из папки
    const lesson = allLessons().find(item => item.id === id);
    if (!lesson) { toast("Урока нет в текущем каталоге. Обновите курс и попробуйте снова."); return; }
    ++progressRevision;
    const previous = state.progress[id];
    const wasDone = effectiveStatus(lesson) === "done";
    // снятие отметки возвращает статус семени преподавателя; для done-семени явно ставим not-started
    const status = wasDone ? lesson.seed_status === "done" ? "not-started" : null : "done";
    if (status) state.progress[id] = { status }; else delete state.progress[id];
    state.pending.add(id);
    updateCompletionUI();
    try {
      const data = await request("/api/progress", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ lesson_id: id, status }) });
      // Update this lesson only: another lesson may have an optimistic save in flight.
      if (data.items?.[id]) state.progress[id] = data.items[id]; else delete state.progress[id];
      toast(wasDone ? "Отметка снята" : "Урок отмечен пройденным");
    } catch (error) {
      if (previous) state.progress[id] = previous; else delete state.progress[id];
      toast("Не удалось сохранить отметку. Попробуйте ещё раз.");
    } finally { ++progressRevision; state.pending.delete(id); updateCompletionUI(); }
  }
  document.addEventListener("click", event => {
    if (event.target.closest(".skip-link")) {
      event.preventDefault();
      $("#main").focus();
      return;
    }
    const button = event.target.closest("[data-action]");
    if (!button) return;
    if (button.dataset.action === "complete") toggleCompletion(button.dataset.id);
    if (button.dataset.action === "reload") loadCatalog();
    if (button.dataset.action === "filter") {
      const filter = button.dataset.filter;
      state.filter = filter;
      renderRoute().then(() => {
        [...content.querySelectorAll('[data-action="filter"]')].find(item => item.dataset.filter === filter)?.focus({ preventScroll: true });
      });
    }
  });
  content.addEventListener("toggle", event => {
    const details = event.target;
    if (!details.dataset.track) return;
    if (details.open) state.openTracks.add(details.dataset.track); else state.openTracks.delete(details.dataset.track);
  }, true);
  $("#refresh").addEventListener("click", () => loadCatalog());
  function submitSearch(push = false) {
    clearTimeout(searchTimer);
    const hash = `#search/${encodeURIComponent($("#search").value.trim())}`;
    if (location.hash === hash) { renderRoute(); return; }
    if (push) location.hash = hash;              // Enter — шаг в истории «Назад»
    else { history.replaceState(null, "", hash); renderRoute(); } // набор текста — историю не засоряем
  }
  $("#search-form").addEventListener("submit", event => { event.preventDefault(); submitSearch(true); });
  $("#search").addEventListener("input", () => {
    clearTimeout(searchTimer);
    searchController?.abort();
    ++routeVersion;
    searchTimer = setTimeout(submitSearch, 300);
  });
  document.addEventListener("keydown", event => {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") { event.preventDefault(); $("#search").focus(); }
  });
  window.addEventListener("hashchange", () => { clearTimeout(searchTimer); renderRoute({ focus: route().page !== "search" }); });
  window.addEventListener("focus", () => { if (state.catalog) loadCatalog({ quiet: true }); });
  document.addEventListener("visibilitychange", () => { if (!document.hidden && state.catalog) loadCatalog({ quiet: true }); });
  setInterval(() => { if (!document.hidden && state.catalog) loadCatalog({ quiet: true }); }, 60000);
  loadCatalog();
})();
