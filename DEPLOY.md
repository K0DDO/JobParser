# JobParser — деплой на Linux VPS

Headless backend (Docker): парсинг по расписанию + Telegram-карточки для новых matched-вакансий.
Flutter на сервере не нужен.

## 1. Первый запуск на VPS

```bash
sudo mkdir -p /opt/jobparser
sudo chown "$USER":"$USER" /opt/jobparser
git clone https://github.com/K0DDO/JobParser.git /opt/jobparser
cd /opt/jobparser
cp .env.example .env
nano .env   # заполнить секреты
```

Обязательные переменные в `.env`:

- `POSTGRES_*`, `DATABASE_URL`, `REDIS_URL`
- HH: `HH_CLIENT_ID`, `HH_CLIENT_SECRET`, `HH_USER_AGENT`, `HH_REDIRECT_URI`
- Telegram: `TELEGRAM_ENABLED=true`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`

Запуск (prod-порты только на localhost):

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
curl -s http://127.0.0.1:8000/api/v1/health
```

## 2. Telegram chat_id

1. Создай бота у [@BotFather](https://t.me/BotFather), получи токен → `TELEGRAM_BOT_TOKEN`.
2. Напиши боту `/start` (личный чат) или добавь бота в канал как admin.
3. Узнай chat_id:

```bash
curl -s "https://api.telegram.org/bot<TOKEN>/getUpdates" | jq
```

Для личного чата — `message.chat.id`. Для канала — обычно `-100…`.

4. Пропиши `TELEGRAM_CHAT_ID` в `.env` и перезапусти backend:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d backend
```

## 3. Автодеплой GitHub Actions

Workflow: `.github/workflows/deploy.yml` (push в `main` или вручную).

Секреты репозитория (Settings → Secrets and variables → Actions):

| Secret | Пример |
|--------|--------|
| `VPS_HOST` | `1.2.3.4` |
| `VPS_USER` | `deploy` |
| `VPS_SSH_KEY` | приватный SSH-ключ (целиком, включая `BEGIN/END`) |
| `VPS_DEPLOY_PATH` | `/opt/jobparser` |

На VPS:

```bash
# публичный ключ в ~/.ssh/authorized_keys пользователя VPS_USER
# git remote должен быть доступен (HTTPS token или deploy key)
cd /opt/jobparser
git remote -v
```

После настройки каждый push в `main` делает `git reset --hard origin/main` и `docker compose up -d --build`.

Если на сервере используешь prod-override, поправь команду в workflow на:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

## 4. Проверка карточек

1. В UI/API создай активный профиль поиска (skills/roles).
2. `POST http://127.0.0.1:8000/api/v1/sync` (или дождись scheduler).
3. Новая вакансия, прошедшая профиль → фото-баннер + текст в Telegram.
4. Повторный sync ту же вакансию не шлёт (`telegram_notified_at`).

Логи:

```bash
docker compose logs backend --tail 80 | grep -i telegram
```

## 5. Firewall

Наружу: `22` (SSH), при необходимости `80/443` (nginx/Caddy → `127.0.0.1:8000`).
Postgres/Redis не публиковать в интернет.
