# Принятые решения

Короткий журнал решений, которые не следуют напрямую из `CLAUDE.md`.

| Дата | Решение |
|---|---|
| 2026-10-26 | Платформенные роли (`user` / `moderator` / `admin`) не добавляются в `User` до задачи «Роли и права» (Sprint 9). |
| 2026-10-26 | Валюта MVP — только RUB. Поле `currency` в моделях денег не нужно; суммы — копейки в `BigIntegerField`. |
| 2026-10-26 | REST API аутентификации — `allauth.headless` (клиент `browser`, сессии + CSRF) под `/api/auth/`. Его OpenAPI-спецификация отдаётся allauth отдельно от drf-spectacular: `/api/auth/openapi.html`. |
