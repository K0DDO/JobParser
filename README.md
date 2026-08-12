# JobParser

Локальное приложение для автоматизированного поиска вакансий.

AI / LLM / embeddings **не используются**. Релевантность определяется детерминированными фильтрами Search Profiles.

## Requirements

- Docker + Docker Compose
- Python 3.12+ (для локальных тестов)
- Flutter 3.22+ (для frontend)
- PostgreSQL и Redis поднимаются через Docker Compose

## Installation

```bash
git clone https://github.com/K0DDO/JobParser.git
cd JobParser
cp .env.example .env
```

## Environment variables

См. `.env.example`.

Ключевые:

| Variable | Description |
|---|---|
| `DATABASE_URL` | Async SQLAlchemy URL |
| `REDIS_URL` | Redis URL |
| `SYNC_INTERVAL_MINUTES` | Интервал синхронизации (по умолчанию 60) |
| `HH_ACCESS_TOKEN` | OAuth token HH для автооткликов |
| `HH_USER_AGENT` | Обязательный User-Agent для HH API |

Курсы валют подтягиваются с ЦБ РФ (`cbr-xml-daily.ru`) при старте и каждые 6 часов, кэш в Redis. Fallback — встроенные курсы, если API недоступен. Статус: `GET /api/v1/fx/rates`.

Секреты храните только в `.env` (файл в `.gitignore`).

## Docker setup

```bash
docker compose up -d
docker compose logs -f backend
```

Сервисы:

- `postgres` — БД
- `redis` — координация/очередь
- `backend` — FastAPI на http://localhost:8000

Swagger: http://localhost:8000/docs

Health: http://localhost:8000/api/v1/health

## Database migrations

Миграции применяются автоматически при старте backend:

```bash
alembic upgrade head
```

Ручной запуск внутри контейнера:

```bash
docker compose exec backend alembic upgrade head
```

## Backend launch (без Docker)

```bash
cd backend
python -m venv .venv
# Windows:
.venv\Scripts\activate
pip install -r requirements.txt
set DATABASE_URL=postgresql+asyncpg://jobparser:jobparser_secret@localhost:5432/jobparser
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

## Frontend launch

```bash
cd frontend
flutter pub get
flutter run -d windows
# или chrome:
flutter run -d chrome --dart-define=API_BASE_URL=http://localhost:8000/api/v1
```

По умолчанию API: `http://localhost:8000/api/v1`.

## How to add a source

1. Создайте класс в `backend/app/parsers/`, реализующий `VacancySource`.
2. Зарегистрируйте его в `backend/app/parsers/__init__.py`.
3. Добавьте запись в `DEFAULT_SOURCES` (`settings_service.py`) и migration/seed при необходимости.
4. Включите parsing в UI → Источники.

Автоотклики для источника включаются отдельно и только если `auto_apply_supported=True`.

## How to configure Search Profiles

1. Откройте **Профили**.
2. Создайте профиль (skills, roles, salary, sources…).
3. При следующей синхронизации вакансии будут матчиться по правилам профиля.

## How to enable Auto Apply

Безопасная цепочка:

1. Включите **Dry Run** в Настройках.
2. В профиле включите `Auto Apply` (через API `PATCH /profiles/{id}`).
3. В Источниках включите Auto Apply только для поддерживаемых (HH).
4. На Dashboard нажмите **Включить автоотклики** и подтвердите предупреждение.

Автоотклик уходит только если:

```text
global_auto_apply == true
AND profile_auto_apply == true
AND source_auto_apply == true
AND source supports auto-apply
AND daily limits not exceeded
AND working hours allow
```

Для реального HH apply нужен `HH_ACCESS_TOKEN`.

## How to use Dry Run

1. Settings → Dry Run = ON
2. Включите Global Auto Apply
3. Система поставит элементы в очередь и создаст Application со статусом `dry_run`
4. Реальные HTTP-отклики **не отправляются**

## How to stop Auto Apply

- Dashboard → **Выключить автоотклики**
- или **Emergency Stop** (мгновенно гасит global switch и скипaет pending queue)

## Current source status

| Source | Parsing | Auto Apply |
|---|---|---|
| Habr Career | ✅ public JSON API | ❌ open vacancy in browser |
| Hirify | ✅ public JSON API | ❌ open vacancy in browser |
| Talanto | ✅ public JSON API | ❌ open vacancy in browser |
| GetMatch | ✅ public `/api/offers` (~800 вакансий) | ❌ open vacancy in browser |
| HH | ⏸ paused (no approved app, API 403) | ❌ until HH app is approved |

Фейковые вакансии не генерируются.

## Tests

```bash
cd backend
pip install -r requirements.txt
pytest -q
```

Критические тесты:

- Global Auto Apply OFF → отклики не отправляются
- Daily limit
- Dry run
- Emergency stop
- Filters / dedupe / normalize

## Troubleshooting

**Backend не стартует**

```bash
docker compose logs backend
docker compose ps
```

**HH parser failed: HTTP 403**

HH блокирует `/vacancies` для некоторых сетей/IP (VPN, хостинг, корпоративный NAT).
`/dictionaries` при этом может отвещать 200.

Что сделать:
1. В Amnezia пустите `hh.ru` и `api.hh.ru` **мимо VPN**, не в туннель
2. В `.env` укажите реальный email в `HH_USER_AGENT`
3. После одобрения приложения на https://dev.hh.ru/ вставьте `HH_CLIENT_ID` и `HH_CLIENT_SECRET`
4. Откройте http://localhost:8000/api/v1/auth/hh/login и разрешите доступ
5. Нажмите «Синхронизировать сейчас»

Проверка статуса: http://localhost:8000/api/v1/auth/hh/status`

**HH parser failed: Bad User-Agent**

Не используйте `example.com` в User-Agent — HH его блокирует.

**Auto-apply failed: token**

Установите `HH_ACCESS_TOKEN` из [HH OAuth](https://dev.hh.ru/).

**Flutter не видит API**

Убедитесь, что backend доступен на `localhost:8000`, CORS включён (уже в приложении).

**Sync already in progress**

Дождитесь завершения или перезапустите backend.

## Project structure

```text
backend/app/
  api/ parsers/ services/ automation/ scheduler/ models/ schemas/
frontend/lib/
  screens/ widgets/ services/ models/ core/
```

## License

Private / local use.
