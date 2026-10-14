"use strict";

// Только представление документов: исходный Markdown и отметки не изменяются.
(() => {
  const md = window.markdownit({ html: false, linkify: true, typographer: false });
  const esc = md.utils.escapeHtml;
  const slug = text => text.toLowerCase().replace(/[^\p{L}\p{N}_-]+/gu, "-").replace(/^-+|-+$/g, "") || "section";
  const textContent = tokens => (tokens || []).map(token => {
    if (token.type === "image") return token.content;
    if (token.children) return textContent(token.children);
    return ["text", "code_inline"].includes(token.type) ? token.content : token.type === "softbreak" ? " " : "";
  }).join("");

  function linkInfo(href, env) {
    try {
      if (href.startsWith("#")) {
        const fragment = decodeURIComponent(href.slice(1));
        const anchor = env.headings.find(item => item.slug === fragment || item.id === fragment);
        return anchor ? { href: `#${anchor.id}`, anchor: anchor.id } : null;
      }
      const url = new URL(href, env.baseURL);
      if (!["http:", "https:", "mailto:"].includes(url.protocol)) return null;
      return env.resolveLink ? env.resolveLink(url) : { href: url.href, external: true };
    } catch { return null; }
  }
  md.renderer.rules.link_open = (tokens, index, options, env, renderer) => {
    const token = tokens[index];
    const link = linkInfo(token.attrGet("href") || "", env);
    if (!link) {
      token.attrSet("href", "#");
      token.attrSet("data-unavailable-link", "true");
      token.attrSet("title", "Ссылка недоступна в портале");
    } else {
      token.attrSet("href", link.href);
      if (link.anchor) token.attrSet("data-document-anchor", link.anchor);
      if (link.external) {
        token.attrSet("target", "_blank");
        token.attrSet("rel", "noopener noreferrer");
      }
    }
    return renderer.renderToken(tokens, index, options);
  };
  // Изображения не загружаются из внешних источников при чтении документа.
  md.renderer.rules.image = (tokens, index, options, env) => {
    const token = tokens[index];
    const label = textContent(token.children) || token.content || "Изображение";
    const link = linkInfo(token.attrGet("src") || "", env);
    return link ? `<a class="document-image-link" href="${esc(link.href)}"${link.anchor ? ` data-document-anchor="${esc(link.anchor)}"` : ""}${link.external ? ' target="_blank" rel="noopener noreferrer"' : ""}>${esc(label)}</a>` : esc(label);
  };
  md.renderer.rules.table_open = () => '<div class="document-table" role="region" aria-label="Таблица документа" tabindex="0"><table>\n';
  md.renderer.rules.table_close = () => "</table></div>\n";
  md.renderer.rules.th_open = (tokens, index, options, env, renderer) => {
    tokens[index].attrSet("scope", "col");
    return renderer.renderToken(tokens, index, options);
  };
  md.core.ruler.after("inline", "document_structure", state => {
    const used = new Map();
    state.env.headings = [];
    for (let i = 0; i < state.tokens.length; i++) {
      const token = state.tokens[i];
      if (token.type === "heading_open") {
        const text = textContent(state.tokens[i + 1]?.children);
        const base = slug(text), count = used.get(base) || 0;
        used.set(base, count + 1);
        const unique = base + (count ? `-${count}` : "");
        const id = `document-section-${unique}`;
        token.attrSet("id", id);
        token.attrSet("tabindex", "-1");
        state.env.headings.push({ id, slug: unique, text, level: Number(token.tag.slice(1)) });
      }
      if (token.type === "list_item_open") {
        const inline = state.tokens[i + 2];
        const first = inline?.type === "inline" && inline.children?.[0];
        const task = first?.type === "text" && /^\[([ xX])\]\s+/.exec(first.content);
        if (!task) continue;
        const done = task[1].toLowerCase() === "x";
        first.content = first.content.slice(task[0].length);
        token.attrJoin("class", "document-task");
        const marker = new state.Token("html_inline", "", 0);
        marker.content = `<span class="document-task-mark${done ? " done" : ""}" role="img" aria-label="${done ? "Выполнено" : "Не выполнено"}">${done ? "✓" : "○"}</span> `;
        inline.children.unshift(marker);
      }
    }
  });

  window.VibeCMarkdown = {
    render(source, { baseURL, resolveLink } = {}) {
      const env = { baseURL, resolveLink, headings: [] };
      const html = md.render(source, env);
      return { html, headings: env.headings, readingMinutes: Math.max(1, Math.ceil(source.trim().split(/\s+/).length / 180)) };
    },
  };
})();
