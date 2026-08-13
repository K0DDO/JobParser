# JobParser

Локальный агрегатор вакансий: FastAPI + Postgres + Flutter. Без LLM.

Собирает объявления с джоб-бордов, приводит зарплаты к **₽ / месяц**, фильтрует по профилю поиска.

```bash
docker compose up -d
cd frontend && flutter run -d windows
```

API: http://localhost:8000/docs

## Платформы

- [Habr Career](https://career.habr.com)
- [Hirify](https://hirify.me)
- [Talanto](https://talanto.work)
- [GetMatch](https://getmatch.ru)
- [Remote OK](https://remoteok.com)
- [Remotive](https://remotive.com)
- [Himalayas](https://himalayas.app)
- [Jobicy](https://jobicy.com)
- [Arbeitnow](https://www.arbeitnow.com)
- [We Work Remotely](https://weworkremotely.com)
- [Working Nomads](https://www.workingnomads.com/jobs)
- Company careers (Greenhouse / Lever / Ashby): GitLab, JetBrains, Canonical, Stripe, Datadog и др.
- [hh.ru](https://hh.ru) — парсинг на паузе (API 403)
