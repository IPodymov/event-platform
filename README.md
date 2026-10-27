# Турнирная платформа

Веб-платформа киберспортивных турниров на Django. Организаторы проводят турниры, игроки и команды регистрируются, проходят check-in, играют матчи по сетке и отправляют результаты. Призовые фонды формируются из донатов на платформу.

Дисциплины MVP: **CS2**, **Dota 2**, **LoL: Wild Rift** (команды 5 + до 2 запасных) и **Hearthstone** (соло 1v1).

| Документ | Что внутри |
|---|---|
| [`CLAUDE.md`](CLAUDE.md) | Полные требования к продукту и правила разработки — главный источник истины |
| [`docs/tournament_sprints_tasks.csv`](docs/tournament_sprints_tasks.csv) | Бэклог по спринтам |
| [`docs/erd.md`](docs/erd.md) | Модель данных (Mermaid) |
| [`docs/decisions.md`](docs/decisions.md) | Принятые продуктовые и технические решения, открытые вопросы |

## Стек

- Python 3.12, Django 5.2, Django REST Framework, drf-spectacular (OpenAPI)
- PostgreSQL 16, Redis 7, Celery + Celery Beat
- django-allauth: вход по email, привязка Steam (OpenID) и Discord (OAuth), REST API аутентификации (`allauth.headless`)
- Frontend MVP: Django Templates (дальше — HTMX + Alpine.js)
- Зависимости — [uv](https://docs.astral.sh/uv/), окружение — Docker Compose
- Качество: ruff, mypy (+ django-stubs), pytest, factory_boy, hypothesis, GitHub Actions

## Быстрый старт (Docker)

Нужны Docker с Compose v2.24+ и, для локальных команд, `uv`.

```bash
cp .env.example .env            # заполните DJANGO_SECRET_KEY и POSTGRES_PASSWORD
./scripts/dev.sh                # сборка и запуск всего стека на переднем плане
```

Во втором терминале — первичная настройка БД:

```bash
docker compose run --rm web python manage.py migrate
docker compose run --rm web python manage.py createsuperuser --email admin@example.com
```

После запуска:

| Адрес | Что это |
|---|---|
| http://localhost:8000/ | Сайт |
| http://localhost:8000/admin/ | Админка |
| http://localhost:8000/api/docs/ | Swagger UI основного API |
| http://localhost:8000/api/redoc/ | ReDoc основного API |
| http://localhost:8000/api/auth/openapi.html | OpenAPI аутентификации (allauth) |
| http://localhost:8000/api/health/ | Проверка живости (БД) |

Письма (подтверждение email, сброс пароля) в dev выводятся в лог сервиса `web`: `docker compose logs -f web`.

### Остановка

`./scripts/dev.sh` держит стек на переднем плане. **Ctrl+C** корректно останавливает все сервисы, затем удаляет контейнеры и сеть — порты web, PostgreSQL и Redis освобождаются. Данные БД сохраняются в томе `postgres_data`.

Если стек запущен в фоне (`docker compose up -d`), Ctrl+C на него не действует — остановите его командой:

```bash
docker compose down            # контейнеры и сеть удаляются, порты освобождаются
docker compose down -v         # то же + удалить данные БД (том postgres_data)
```

### Сервисы

| Сервис | Назначение |
|---|---|
| `web` | Django (`runserver` с автоперезагрузкой; код смонтирован в контейнер) |
| `worker` | Celery worker — фоновые задачи |
| `beat` | Celery Beat — периодические задачи (переходы статусов и т.п.) |
| `db` | PostgreSQL 16 |
| `redis` | Кэш, брокер Celery, rate limiting |

Порты на хосте настраиваются в `.env` (`WEB_HOST_PORT`, `POSTGRES_HOST_PORT`, `REDIS_HOST_PORT`) и слушают только `127.0.0.1`.

После изменения зависимостей (`pyproject.toml`/`uv.lock`) пересоберите образ — `./scripts/dev.sh` делает это сам (`--build`). Иначе `runserver` подхватит новый код через смонтированный том и упадёт без новых пакетов.

## Локальная разработка без Docker для Django

БД и Redis удобно держать в Docker, а Django и тесты запускать на хосте:

```bash
uv sync                                   # создаёт .venv с Python 3.12 и всеми зависимостями
docker compose up -d db redis             # только инфраструктура
set -a; source .env; set +a               # DATABASE_URL и REDIS_URL должны указывать на localhost и порты из .env
uv run python manage.py migrate
uv run python manage.py runserver         # Ctrl+C останавливает сервер и освобождает порт
```

`manage.py` по умолчанию использует `config.settings.dev`.

## Команды разработки

```bash
uv run ruff check .                       # линтер
uv run ruff format .                      # форматирование
uv run mypy .                             # типы (strict для brackets, matches, payments, prizes)
uv run pytest                             # тесты + отчёт покрытия; нужен запущенный PostgreSQL
uv run pytest apps/teams -x --no-cov      # часть тестов, без покрытия
HYPOTHESIS_PROFILE=ci uv run pytest       # больше примеров для property-based тестов

uv run python manage.py makemigrations --check --dry-run   # нет ли забытых миграций
uv run python manage.py spectacular --validate --fail-on-warn --file /dev/null   # схема OpenAPI

# Переводы (язык интерфейса по умолчанию — русский); нужен gettext
uv run python manage.py makemessages -l ru --ignore=.venv --ignore=venv --no-location
uv run python manage.py compilemessages --ignore=.venv --ignore=venv
```

Тесты всегда идут с `config.settings.test` (флаг `--ds` в `pyproject.toml`), даже если в окружении экспортирован другой `DJANGO_SETTINGS_MODULE`.

CI (`.github/workflows/ci.yml`) на каждый PR и push в `main` запускает ruff, mypy, тесты на PostgreSQL и Redis, проверку миграций и схемы OpenAPI, сборку Docker-образа.

## Структура проекта

```
config/                настройки и инфраструктура
  settings/            base, dev, staging, prod, test
  exceptions.py        DomainError, DomainPermissionError и их рендеринг в DRF
  images.py            проверка и перекодирование загружаемых изображений
  celery.py, urls.py, views.py (health)
apps/
  accounts/            User (вход по email), Profile, GameAccount, адаптеры allauth
  games/               Game, MapPool, регионы и типы игровых ID (regions.py)
  teams/               Team, TeamMembership, TeamInvite
  tournaments/ brackets/ matches/ notifications/ integrations/ moderation/ payments/ prizes/
                       заготовки приложений следующих спринтов
templates/             шаблоны страниц
locale/ru/             русский каталог переводов (.po и скомпилированный .mo)
scripts/dev.sh         запуск dev-стека с остановкой по Ctrl+C
docs/                  ERD, решения, бэклог
```

Внутри приложения:

| Файл | Что там |
|---|---|
| `models.py` | Модели и ограничения БД (`CheckConstraint`, частичные уникальные индексы) |
| `services.py` | **Вся бизнес-логика**: проверки, транзакции, блокировки строк, права |
| `selectors.py` | Чтение сложных выборок |
| `exceptions.py` | Доменные ошибки приложения |
| `views.py`, `forms.py` | Тонкие страницы: валидация ввода → вызов сервиса → ответ |
| `api/` | Тонкий REST API: сериализатор валидирует ввод, сервис выполняет действие |
| `tests/` | Тесты и фабрики (`factories.py`) |

## Архитектурные соглашения

Коротко; полный список — в [`CLAUDE.md`](CLAUDE.md).

- **Бизнес-логика только в сервисах**, не во views, формах, сериализаторах или `save()`. Сервисы принимают аргументы только по имени: `services.team_create(user=..., game=..., ...)`.
- **Доменные ошибки** наследуются от `config.exceptions.DomainError`; атрибут `field` привязывает ошибку к полю ввода. API отдаёт их как **400** (`{"field": ["сообщение"]}`), а `DomainPermissionError` — как **403**. Страницы показывают их в форме или через сообщения.
- **Изменения нескольких записей** — в `transaction.atomic()` с `select_for_update()`. Например, изменения состава команды блокируют строку команды, поэтому параллельные вступления не переполняют состав (покрыто тестами с потоками).
- **Инварианты — в БД**, а не только в коде: одна активная команда игрока в дисциплине, один капитан, один активный пул карт, уникальность ников, названий и тегов без учёта регистра.
- **Время** хранится в UTC и показывается в часовом поясе из профиля (`UserTimezoneMiddleware`).
- **Строки интерфейса** — через `gettext` на английском в коде, перевод — в `locale/ru`.
- **Загружаемые изображения** (аватары, логотипы) проверяются по размеру, формату и числу пикселей и перекодируются в WebP (`config/images.py`).
- Новые зависимости добавляются только с объяснением в сообщении коммита. Один логический коммит на задачу, Conventional Commits.

## API

Основное API — `/api/v1/`, схема в `/api/docs/`. Аутентификация — сессия + CSRF (заголовок `X-CSRFToken`), вход и регистрация — через `/api/auth/browser/v1/` (allauth headless, своя спецификация в `/api/auth/openapi.html`).

| Ресурс | Эндпоинты |
|---|---|
| Профиль | `GET/PATCH /api/v1/me/profile/` (JSON или multipart с `avatar`) |
| Игровые аккаунты | `GET/POST /api/v1/me/game-accounts/`, `PATCH/DELETE /api/v1/me/game-accounts/<id>/` |
| Публичный профиль | `GET /api/v1/players/<nickname>/` |
| Дисциплины | `GET /api/v1/games/`, `GET /api/v1/games/<slug>/map-pool/` |
| Команды | `GET/POST /api/v1/teams/` (`?game=cs2`), `GET /api/v1/teams/<id>/` |
| Состав | `PATCH/DELETE /api/v1/teams/<id>/members/<membership_id>/`, `POST /api/v1/teams/<id>/transfer-captaincy/`, `POST /api/v1/teams/<id>/leave/` |
| Приглашения | `GET/POST /api/v1/teams/<id>/invites/`, `DELETE /api/v1/teams/<id>/invites/<invite_id>/`, `GET /api/v1/me/invites/`, `GET /api/v1/invites/<token>/`, `POST /api/v1/invites/<token>/accept/` и `/decline/` |

Пример: регистрация через API с ником (подтверждение email обязательно):

```bash
curl -c jar -b jar http://localhost:8000/accounts/login/ >/dev/null      # получить csrftoken
TOKEN=$(awk '/csrftoken/ {print $7}' jar)
curl -b jar -c jar -H "X-CSRFToken: $TOKEN" -H "Content-Type: application/json" \
     -d '{"email":"me@example.com","nickname":"my_nick","password":"S3cure-pass-42"}' \
     http://localhost:8000/api/auth/browser/v1/auth/signup
```

## Переменные окружения

Полный список с примерами — в [`.env.example`](.env.example). Основные:

| Переменная | Назначение |
|---|---|
| `DJANGO_SECRET_KEY` | Секретный ключ Django (обязательно) |
| `DATABASE_URL` | Подключение к PostgreSQL |
| `REDIS_URL`, `CELERY_BROKER_URL` | Кэш и брокер Celery |
| `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS` | Хосты и доверенные источники (staging/prod) |
| `EMAIL_URL`, `DEFAULT_FROM_EMAIL` | Отправка писем (`consolemail://` в dev, `smtp+tls://…` в prod) |
| `STEAM_API_KEY` | Steam Web API — ник и аватар после входа через Steam |
| `DISCORD_CLIENT_ID`, `DISCORD_CLIENT_SECRET` | Discord OAuth; redirect URI — `<сайт>/accounts/discord/login/callback/` |
| `ALLAUTH_TRUSTED_PROXY_COUNT` | Число прокси перед приложением (для IP в rate limiting) |
| `WEB_HOST_PORT`, `POSTGRES_HOST_PORT`, `REDIS_HOST_PORT` | Порты Docker на хосте |

Модуль настроек выбирается вне `.env`: `manage.py` → `config.settings.dev`, pytest → `config.settings.test`, серверы задают `DJANGO_SETTINGS_MODULE=config.settings.staging` или `config.settings.prod`. Никогда не коммитьте `.env` и секреты.

## Что уже работает

**Аккаунты.** Регистрация по email с обязательным подтверждением, вход, сброс пароля, rate limiting. Ник указывается при регистрации. Профиль: аватар, страна, часовой пояс, «о себе». Привязка Steam и Discord — только к существующему аккаунту, после неё можно входить через провайдера.

**Игровые аккаунты.** SteamID64 для CS2 и Dota 2 создаётся автоматически из привязанного Steam и сразу подтверждён. Riot ID (Wild Rift) и BattleTag (Hearthstone) игрок вводит сам вместе с регионом, подтверждает их staff действием в админке. Публичная страница игрока — `/players/<nickname>/`.

**Дисциплины.** Справочник CS2, Dota 2, Wild Rift, Hearthstone создаётся миграцией. Пул карт CS2 ведётся в админке; активный пул — ровно 7 карт. **Стартовый пул не засеян** — создайте и активируйте его в админке.

**Команды.** Создание (создатель — капитан), приглашения по нику или ссылке (7 дней), роли игрок/запасной в пределах состава, передача капитанства, исключение, уход; последний участник, уходя, распускает команду.

Дальше по плану: проверка игровых аккаунтов в составе, затем турниры (Sprint 3). Статус задач — в бэклоге, решения и открытые вопросы — в [`docs/decisions.md`](docs/decisions.md).

## Частые проблемы

- **`port is already allocated` при запуске.** Порт занят другим проектом. Поменяйте `WEB_HOST_PORT`, `POSTGRES_HOST_PORT` или `REDIS_HOST_PORT` в `.env` и поправьте порт в `DATABASE_URL`/`REDIS_URL` для запуска на хосте. Остатки собственного стека убирает `docker compose down`.
- **`ModuleNotFoundError` в контейнере после `git pull`.** Образ собран со старыми зависимостями — перезапустите `./scripts/dev.sh` (пересобирает образ) или выполните `docker compose build`.
- **В шаблоне на странице виден текст `{{ ... }}`.** Тег Django разбит на несколько строк (часто это делает автоформатирование IDE) — Django такие теги не распознаёт. Тест `tests/test_settings.py::test_templates_have_no_multiline_tags` ловит это; отключите перенос длинных строк для HTML-шаблонов в настройках IDE.
- **Кнопки Steam/Discord ведут на ошибку.** Не заданы `STEAM_API_KEY` или `DISCORD_CLIENT_ID`/`DISCORD_CLIENT_SECRET` в `.env`.
- **Сообщения интерфейса на английском.** Новые строки ещё не переведены — выполните `makemessages`, добавьте переводы в `locale/ru/LC_MESSAGES/django.po` и `compilemessages`.
