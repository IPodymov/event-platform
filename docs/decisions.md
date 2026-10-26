# Принятые решения

Короткий журнал решений, которые не следуют напрямую из `CLAUDE.md`.

| Дата | Решение |
|---|---|
| 2026-10-26 | Платформенные роли (`user` / `moderator` / `admin`) не добавляются в `User` до задачи «Роли и права» (Sprint 9). |
| 2026-10-26 | Валюта MVP — только RUB. Поле `currency` в моделях денег не нужно; суммы — копейки в `BigIntegerField`. |
| 2026-10-26 | REST API аутентификации — `allauth.headless` (клиент `browser`, сессии + CSRF) под `/api/auth/`. Его OpenAPI-спецификация отдаётся allauth отдельно от drf-spectacular: `/api/auth/openapi.html`. |
| 2026-10-26 | Steam (и другие сторонние провайдеры) — только привязка к существующему email-аккаунту и последующий вход. Регистрация через провайдера запрещена (`SocialAccountAdapter.is_open_for_signup`). Не больше одного Steam-аккаунта на пользователя. Steam ID хранится в `allauth.socialaccount.SocialAccount` (`provider="steam"`, `uid` = SteamID64), читается через `apps.accounts.selectors.get_steam_id`. |
