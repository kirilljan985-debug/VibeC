# Локальная сборка Markdown

`markdown-it.min.js` — официальная браузерная UMD-сборка **markdown-it 15.0.2**.
Приложение загружает её с локального сервера; доступ к интернету для чтения документов не нужен.

- Проект: https://github.com/markdown-it/markdown-it
- Документация: https://markdown-it.github.io/markdown-it/
- Источник: https://registry.npmjs.org/markdown-it/-/markdown-it-15.0.2.tgz
- Файл в архиве: `package/dist/browser/markdown-it.umd.min.js`.
- SHA-512 архива (SRI): `sha512-q4IGxMv56jCqT4OCRCADBoDP3LO4MhmTXjFbphHPXs4g3j9Xg5RDnxqN8IF/3vIWEU+VCnUq+7JUg/cfy2E6Qw==`.
- Лицензия MIT сохранена без изменений в `markdown-it.LICENSE`.

Контрольная сумма архива проверена перед копированием. Сборка сохранена без изменения кода.
Настройки приложения и собственные правила рендера находятся в `../markdown.js`:
HTML из документов выключен, автоматическая загрузка изображений отключена,
ссылки проверяются, исходные Markdown-файлы не записываются.
