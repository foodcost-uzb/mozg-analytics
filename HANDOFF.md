# MOZG Analytics - Project Handoff

**Дата:** 2026-02-01
**Статус:** Phase 3 завершена
**Готовность:** Full-stack приложение готово к развёртыванию

---

## 1. Обзор проекта

**MOZG Analytics** — BI-платформа для ресторанного бизнеса, аналог MOZG REST.

### Цели проекта
- Интеграция с POS-системами (iiko, R-Keeper)
- Аналитика продаж и меню
- Прогнозирование выручки и спроса
- Доступ через Telegram Bot + Mini App + Web Dashboard

### Технологический стек
| Компонент | Технология | Версия |
|-----------|------------|--------|
| Backend API | FastAPI | 0.109.0 |
| Database | PostgreSQL | 15 |
| Cache | Redis | 7 |
| Task Queue | Celery | 5.3.6 |
| ORM | SQLAlchemy | 2.0.25 (async) |
| Auth | JWT + Telegram OAuth | python-jose |

---

## 2. Структура проекта

```
mozg-analytics/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── deps.py              # Зависимости, RBAC
│   │   │   └── v1/
│   │   │       ├── auth.py          # Авторизация endpoints
│   │   │       ├── organizations.py # Управление организацией
│   │   │       ├── venues.py        # CRUD заведений
│   │   │       ├── schemas.py       # Pydantic схемы
│   │   │       └── router.py        # Роутер API
│   │   ├── core/
│   │   │   ├── config.py            # Настройки приложения
│   │   │   ├── security.py          # JWT, пароли, Telegram auth
│   │   │   └── celery_app.py        # Конфигурация Celery
│   │   ├── db/
│   │   │   ├── base.py              # Базовые классы моделей
│   │   │   ├── models.py            # SQLAlchemy модели (10 таблиц)
│   │   │   └── session.py           # Async сессия БД
│   │   ├── integrations/
│   │   │   ├── iiko/
│   │   │   │   ├── client.py        # iiko Cloud API клиент
│   │   │   │   └── schemas.py       # Схемы данных iiko
│   │   │   └── rkeeper/             # [Placeholder]
│   │   ├── services/
│   │   │   ├── sync/
│   │   │   │   ├── iiko_sync.py     # Сервис синхронизации iiko
│   │   │   │   └── tasks.py         # Celery задачи
│   │   │   ├── reports/
│   │   │   │   ├── sales.py         # SalesReportService
│   │   │   │   └── menu.py          # MenuAnalysisService (ABC/XYZ/Go-List)
│   │   │   ├── export/
│   │   │   │   └── excel.py         # ExcelExportService
│   │   │   ├── cache.py             # Redis кеширование
│   │   │   └── analytics/           # [Phase 4]
│   │   └── main.py                  # FastAPI приложение
│   ├── alembic/
│   │   ├── env.py
│   │   └── versions/
│   │       └── 001_initial_schema.py
│   ├── tests/
│   │   ├── conftest.py              # Pytest фикстуры
│   │   ├── test_auth.py
│   │   └── test_venues.py
│   ├── alembic.ini
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example
├── frontend/                         # Vue.js 3 Dashboard
│   ├── src/
│   │   ├── api/                      # Axios API клиент
│   │   ├── components/               # UI компоненты
│   │   │   ├── layout/               # AppHeader, AppSidebar
│   │   │   ├── common/               # StatCard, DataTable, DateRangePicker
│   │   │   └── charts/               # ECharts компоненты
│   │   ├── stores/                   # Pinia stores
│   │   ├── views/                    # Dashboard, Sales, Menu, Settings, Login
│   │   ├── router/                   # Vue Router
│   │   └── types/                    # TypeScript типы
│   ├── package.json
│   ├── vite.config.ts
│   └── tailwind.config.js
├── telegram/                         # [Phase 6 - Bot + Mini App]
├── docker-compose.yml
├── CLAUDE.md                         # Документация для разработки
└── .gitignore
```

---

## 3. База данных

### Схема (10 таблиц)

```
organizations (мультитенант)
    └── users (роли: owner, admin, manager, analyst, viewer)
    └── venues (заведения с POS конфигом)
            ├── categories (категории меню)
            ├── products (позиции меню)
            ├── employees (сотрудники)
            ├── receipts (чеки)
            │       └── receipt_items (позиции чека)
            ├── daily_sales (агрегаты по дням)
            └── hourly_sales (агрегаты по часам)
```

### Ключевые особенности
- UUID первичные ключи
- Мультитенант архитектура (organization_id)
- JSONB для гибких конфигов (pos_config, settings)
- Индексы для быстрых запросов по датам
- Уникальные ограничения venue_id + external_id

---

## 4. API Endpoints

### Авторизация `/api/v1/auth`
| Метод | Endpoint | Описание |
|-------|----------|----------|
| POST | `/register` | Регистрация организации + пользователя |
| POST | `/login` | Вход по email/password |
| POST | `/telegram` | Вход через Telegram Mini App |
| POST | `/refresh` | Обновление токена |
| GET | `/me` | Текущий пользователь |

### Организации `/api/v1/organizations`
| Метод | Endpoint | Роль | Описание |
|-------|----------|------|----------|
| GET | `/current` | any | Текущая организация |
| PATCH | `/current` | owner | Обновить организацию |
| GET | `/users` | owner | Список пользователей |
| POST | `/users` | owner | Создать пользователя |
| PATCH | `/users/{id}` | owner | Обновить пользователя |
| DELETE | `/users/{id}` | owner | Удалить пользователя |

### Заведения `/api/v1/venues`
| Метод | Endpoint | Роль | Описание |
|-------|----------|------|----------|
| GET | `` | any | Список заведений |
| POST | `` | admin | Создать заведение |
| GET | `/{id}` | any | Детали заведения |
| PATCH | `/{id}` | admin | Обновить заведение |
| DELETE | `/{id}` | admin | Удалить заведение |
| POST | `/{id}/sync` | manager | Запустить синхронизацию |
| GET | `/{id}/sync/status` | any | Статус синхронизации |

### Отчёты по продажам `/api/v1/reports/sales`
| Метод | Endpoint | Описание |
|-------|----------|----------|
| GET | `/summary` | Сводка продаж за период |
| GET | `/daily` | Ежедневная разбивка |
| GET | `/comparison` | Сравнение с прошлым периодом |
| GET | `/by-venue` | Разбивка по заведениям |
| GET | `/hourly` | Почасовая аналитика |
| GET | `/plan-fact` | План/факт выполнения |
| GET | `/top-days` | Топ дней по выручке |
| GET | `/weekday-analysis` | Анализ по дням недели |

### Анализ меню `/api/v1/reports/menu`
| Метод | Endpoint | Описание |
|-------|----------|----------|
| GET | `/abc` | ABC-анализ (по выручке/прибыли/количеству) |
| GET | `/margin` | Маржинальность продуктов |
| GET | `/go-list` | Go-List матрица рекомендаций |
| GET | `/top-sellers` | Топ продаваемых блюд |
| GET | `/worst-sellers` | Аутсайдеры меню |
| GET | `/categories` | Анализ по категориям |

### Экспорт `/api/v1/reports/export`
| Метод | Endpoint | Описание |
|-------|----------|----------|
| GET | `/sales` | Экспорт продаж в Excel |
| GET | `/abc` | Экспорт ABC-анализа в Excel |
| GET | `/go-list` | Экспорт Go-List в Excel |
| GET | `/margin` | Экспорт маржинальности в Excel |

---

## 5. iiko Интеграция

### Реализовано
- Авторизация с автообновлением токена (60 мин TTL)
- Получение организаций
- Синхронизация номенклатуры (категории, продукты)
- Синхронизация сотрудников
- OLAP отчёты по продажам
- Retry логика с exponential backoff

### Конфигурация venue.pos_config
```json
{
  "organization_id": "uuid-from-iiko",
  "api_login": "your-api-login"
}
```

### Celery задачи
- `sync_venue_data` — синхронизация одного заведения
- `full_sync_all_venues` — полная синхронизация (ежедневно 3:00)
- `incremental_sync_all_venues` — инкрементальная (каждые 15 мин)
- `aggregate_daily_sales` — агрегация дневных продаж (0:05)

---

## 6. Запуск проекта

### Docker (рекомендуется)
```bash
cd mozg-analytics
docker compose up -d

# Проверка API
curl http://localhost:8000/health
# Swagger UI: http://localhost:8000/docs

# Frontend (отдельно)
cd frontend
npm install
npm run dev
# Dashboard: http://localhost:3000
```

### Локально
```bash
# 1. Установить PostgreSQL и Redis
brew install postgresql redis
brew services start postgresql redis

# 2. Создать БД
createdb mozg_analytics

# 3. Настроить окружение
cd backend
cp .env.example .env
# Отредактировать .env

# 4. Установить зависимости
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 5. Применить миграции
alembic upgrade head

# 6. Запустить API
uvicorn app.main:app --reload --port 8000

# 7. Запустить Celery (отдельный терминал)
celery -A app.core.celery_app worker --loglevel=info
celery -A app.core.celery_app beat --loglevel=info
```

---

## 7. Переменные окружения

```env
# Обязательные
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/db
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=your-secret-key-min-32-chars

# Telegram (для Mini App auth)
TELEGRAM_BOT_TOKEN=123456:ABC-xyz

# iiko (для синхронизации)
IIKO_API_LOGIN=your-api-login
```

---

## 8. Тестирование

```bash
cd backend
source venv/bin/activate

# Создать тестовую БД
createdb mozg_analytics_test

# Запустить тесты
pytest -v

# С покрытием
pytest --cov=app --cov-report=html
```

### Текущие тесты
- `test_auth.py` — регистрация, логин, /me
- `test_venues.py` — CRUD заведений

---

## 9. Что сделано

### Phase 1: Фундамент ✅
- [x] Структура проекта
- [x] Docker Compose (PostgreSQL, Redis, API, Celery)
- [x] SQLAlchemy модели с миграциями
- [x] JWT авторизация + Telegram OAuth
- [x] RBAC (owner, admin, manager, analyst, viewer)
- [x] CRUD Organizations, Users, Venues
- [x] iiko Cloud API клиент
- [x] Сервис синхронизации данных
- [x] Celery задачи (sync, aggregation)
- [x] Базовые тесты
- [x] Документация (CLAUDE.md)

### Phase 2: Базовые отчёты ✅
- [x] SalesReportService: summary, daily, hourly, comparison, by-venue, plan-fact
- [x] MenuAnalysisService: ABC-анализ, XYZ-анализ, маржинальность
- [x] Go-List матрица рекомендаций (Stars, Workhorses, Puzzles, Dogs)
- [x] Top/worst sellers, category analysis
- [x] Excel экспорт (openpyxl) для всех отчётов
- [x] Redis кеширование (CacheService)
- [x] API endpoints (20+ эндпоинтов)
- [x] Unit тесты для сервисов отчётов

---

## 10. Что нужно сделать

### Phase 3: Web Dashboard ✅
- [x] Vue.js 3 + Vite + TypeScript проект
- [x] Tailwind CSS стилизация
- [x] Pinia stores (auth, venues, filters)
- [x] Vue Router с auth guards
- [x] API клиент с axios (token refresh)
- [x] ECharts графики (Line, Bar, Pie, Heatmap)
- [x] Компоненты: StatCard, DataTable, DateRangePicker, VenueSelector
- [x] Views: Dashboard, Sales, Menu, Settings, Login

### Phase 4: Advanced Analytics (Next)
- [ ] Vue.js 3 + TypeScript проект
- [ ] Pinia stores
- [ ] ECharts графики
- [ ] Dashboard, Sales, Menu, Settings views

### Phase 4: Продвинутая аналитика
- [ ] Motive Marketing (6 факторов)
- [ ] P&L отчёт
- [ ] HR-аналитика
- [ ] Basket analysis

### Phase 5: Прогнозирование
- [ ] Prophet для прогноза выручки
- [ ] Прогноз спроса на блюда
- [ ] Anomaly detection

### Phase 6: Telegram
- [ ] Расширенные команды бота
- [ ] Push-уведомления
- [ ] Mini App интерфейс

### Дополнительно
- [ ] R-Keeper интеграция
- [ ] Логирование (structlog)
- [ ] Мониторинг (Sentry, Prometheus)
- [ ] CI/CD pipeline
- [ ] Production Dockerfile (multi-stage)

---

## 11. Известные ограничения

1. **bcrypt версия**: Используется 4.0.1 для совместимости с passlib
2. **Python 3.9**: Тестировалось на 3.9.6, для 3.11+ возможны изменения в типах
3. **iiko OLAP**: Упрощённая реализация, для production нужна детальная обработка чеков
4. **R-Keeper**: Только placeholder, требуется реализация

---

## 12. Контакты и ресурсы

- **iiko API Docs**: https://api-ru.iiko.services/swagger/ui/index
- **FastAPI Docs**: https://fastapi.tiangolo.com/
- **SQLAlchemy 2.0**: https://docs.sqlalchemy.org/en/20/

---

## Быстрый старт для нового разработчика

```bash
# 1. Клонировать репозиторий
git clone <repo-url>
cd mozg-analytics

# 2. Запустить через Docker
docker compose up -d

# 3. Проверить API
open http://localhost:8000/docs

# 4. Создать тестового пользователя через Swagger UI
# POST /api/v1/auth/register

# 5. Читать CLAUDE.md для деталей разработки
```

---

*Документ создан автоматически. Актуален на момент завершения Phase 1.*
