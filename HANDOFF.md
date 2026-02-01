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

### Phase 4: Продвинутая аналитика (Next)
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

## 13. История разработки (Changelog)

### Commit e1e462a — Phase 1: Foundation (2026-02-01)

**Фундамент BI-платформы — 45 файлов, +4399 строк**

#### Backend Core
| Файл | Описание |
|------|----------|
| `app/main.py` | FastAPI приложение с CORS, lifespan, /health |
| `app/core/config.py` | Pydantic Settings с валидацией окружения |
| `app/core/security.py` | JWT токены (access/refresh), bcrypt пароли, Telegram OAuth HMAC |
| `app/core/celery_app.py` | Celery + Redis broker, расписание задач (crontab) |

#### Database Layer
| Файл | Описание |
|------|----------|
| `app/db/base.py` | Базовые классы: UUIDMixin, TimestampMixin |
| `app/db/models.py` | 10 SQLAlchemy моделей с relationships |
| `app/db/session.py` | Async session factory (asyncpg) |
| `alembic/versions/001_initial_schema.py` | Миграция: все таблицы + индексы |

**Модели данных:**
```
Organization → users[], venues[]
User         → organization, role (Enum: owner/admin/manager/analyst/viewer)
Venue        → organization, pos_type (iiko/rkeeper), pos_config (JSONB)
Category     → venue, products[]
Product      → venue, category, price, cost_price, is_active
Employee     → venue, external_id, name, role
Receipt      → venue, receipt_items[], payment_type, discount
ReceiptItem  → receipt, product, quantity, price, discount
DailySales   → venue, date, revenue, orders_count, avg_check
HourlySales  → venue, date, hour, revenue, orders_count
```

#### API Endpoints
| Файл | Endpoints | Описание |
|------|-----------|----------|
| `app/api/v1/auth.py` | 5 | register, login, telegram, refresh, me |
| `app/api/v1/organizations.py` | 6 | CRUD организации + управление пользователями |
| `app/api/v1/venues.py` | 7 | CRUD заведений + sync endpoints |
| `app/api/deps.py` | — | get_current_user, require_roles, RBAC декораторы |
| `app/api/v1/schemas.py` | — | 25+ Pydantic схем (request/response) |

#### iiko Integration
| Файл | Описание |
|------|----------|
| `app/integrations/iiko/client.py` | Async HTTP клиент с retry (tenacity) |
| `app/integrations/iiko/schemas.py` | Pydantic схемы для iiko API |

**IikoClient методы:**
- `_ensure_token()` — автообновление токена (TTL 60 мин)
- `get_organizations()` — список организаций
- `get_nomenclature()` — категории и продукты
- `get_employees()` — сотрудники
- `get_olap_report()` — продажи (OLAP)

#### Sync Service
| Файл | Описание |
|------|----------|
| `app/services/sync/iiko_sync.py` | IikoSyncService: full/incremental sync |
| `app/services/sync/tasks.py` | Celery tasks с async wrapper |

**Celery задачи:**
| Задача | Расписание | Описание |
|--------|------------|----------|
| `sync_venue_data` | manual | Синхронизация одного заведения |
| `full_sync_all_venues` | 3:00 daily | Полная синхронизация всех |
| `incremental_sync_all_venues` | */15 min | Инкрементальная (последний час) |
| `aggregate_daily_sales` | 0:05 daily | Агрегация в daily_sales |

#### Infrastructure
| Файл | Описание |
|------|----------|
| `docker-compose.yml` | PostgreSQL, Redis, API, Celery Worker, Celery Beat |
| `backend/Dockerfile` | Python 3.9-slim + uvicorn |
| `backend/requirements.txt` | 25 зависимостей |
| `backend/.env.example` | Шаблон переменных окружения |

#### Tests
| Файл | Тесты |
|------|-------|
| `tests/conftest.py` | pytest fixtures: async db, test client, auth helpers |
| `tests/test_auth.py` | register, login, /me endpoints |
| `tests/test_venues.py` | CRUD venues, permissions |

---

### Commit fd075be — Phase 2 & 3 (2026-02-01)

**Отчёты + Vue.js Dashboard — 51 файл, +7113 строк**

#### Phase 2: Reports Backend

| Файл | Описание |
|------|----------|
| `app/services/reports/sales.py` | SalesReportService |
| `app/services/reports/menu.py` | MenuAnalysisService |
| `app/services/export/excel.py` | ExcelExportService |
| `app/services/cache.py` | CacheService (Redis) |
| `app/api/v1/reports.py` | 20+ API endpoints |

**SalesReportService методы:**
| Метод | Возврат | Описание |
|-------|---------|----------|
| `get_summary()` | SalesSummary | Выручка, чеки, средний чек за период |
| `get_daily()` | list[DailySalesData] | Разбивка по дням |
| `get_comparison()` | SalesComparison | Сравнение с прошлым периодом (%, delta) |
| `get_by_venue()` | list[VenueSalesData] | Выручка по заведениям |
| `get_hourly()` | list[HourlySalesData] | Почасовая разбивка |
| `get_plan_fact()` | PlanFactData | План/факт выполнения |
| `get_top_days()` | list[TopDayData] | Топ дней по выручке |
| `get_weekday_analysis()` | list[WeekdayData] | Средние по дням недели |

**MenuAnalysisService методы:**
| Метод | Описание |
|-------|----------|
| `abc_analysis(by='revenue')` | ABC классификация (A=80%, B=95%, C=остаток) |
| `xyz_analysis()` | XYZ по коэффициенту вариации (X<10%, Y<25%, Z>25%) |
| `margin_analysis()` | Маржинальность: (price-cost)/price * 100 |
| `go_list()` | Матрица: Stars/Workhorses/Puzzles/Dogs/Potential/Standard |
| `top_sellers(limit)` | Топ продаж по количеству |
| `worst_sellers(limit)` | Аутсайдеры меню |
| `category_analysis()` | Разбивка по категориям |

**Go-List матрица:**
```
                 High Margin    Low Margin
High Sales    →    Stars         Workhorses
Low Sales     →    Puzzles       Dogs
New Items     →    Potential     Standard
```

**ExcelExportService:**
- Стилизация: цвета для ABC/Go-List, границы, auto-width колонок
- Форматы: export_sales(), export_abc(), export_go_list(), export_margin()

**CacheService:**
- Custom JSONEncoder для Decimal, date, datetime, UUID
- `@cached(ttl, key_builder)` декоратор
- Методы: get(), set(), delete(), invalidate_pattern()

#### Phase 3: Vue.js Frontend

| Категория | Файлы |
|-----------|-------|
| Config | package.json, vite.config.ts, tsconfig.json, tailwind.config.js |
| API Client | src/api/client.ts, auth.ts, venues.ts, reports.ts |
| Stores | src/stores/auth.ts, venues.ts, filters.ts |
| Router | src/router/index.ts (auth guards) |
| Types | src/types/index.ts (TypeScript interfaces) |

**Компоненты:**

| Компонент | Описание |
|-----------|----------|
| `AppHeader.vue` | Navbar с user menu, venue selector |
| `AppSidebar.vue` | Навигация: Dashboard, Sales, Menu, Settings |
| `StatCard.vue` | KPI карточка с иконкой, значением, delta % |
| `DataTable.vue` | Таблица с сортировкой, пагинацией |
| `DateRangePicker.vue` | Выбор периода с presets (сегодня, неделя, месяц) |
| `VenueSelector.vue` | Dropdown выбора заведения |
| `LineChart.vue` | ECharts линейный график |
| `BarChart.vue` | ECharts столбчатый график |
| `PieChart.vue` | ECharts круговая диаграмма |
| `HeatmapChart.vue` | ECharts тепловая карта (часы × дни) |

**Views:**

| View | Функционал |
|------|------------|
| `LoginView.vue` | Email/password форма, remember me |
| `DashboardView.vue` | KPI cards, revenue chart, top products, hourly heatmap |
| `SalesView.vue` | Tabs: overview, daily, venues, hourly + Excel export |
| `MenuView.vue` | Tabs: ABC analysis, Go-List, margins, categories |
| `SettingsView.vue` | Profile, venue management, iiko integration |

**Axios клиент:**
- Interceptor: auto-attach Bearer token
- Response interceptor: 401 → refresh token → retry request
- Base URL: `/api/v1` (Vite proxy в dev)

**Pinia Stores:**
| Store | State | Actions |
|-------|-------|---------|
| auth | user, token, isAuthenticated | login, logout, refreshToken, init |
| venues | venues[], selectedVenue | fetchVenues, selectVenue |
| filters | dateRange, quickFilter | setDateRange, setQuickFilter |

---

## 14. Архитектурные решения

### Backend
1. **Async everywhere**: SQLAlchemy 2.0 async, httpx async, Celery с async wrapper
2. **Multi-tenant**: organization_id во всех таблицах, RBAC через deps.py
3. **Aggregate tables**: daily_sales/hourly_sales для быстрых отчётов
4. **JSONB configs**: pos_config и settings для гибкости без миграций

### Frontend
1. **Composition API**: `<script setup>` во всех компонентах
2. **Pinia**: Reactive stores с persist (localStorage)
3. **ECharts**: vue-echarts wrapper для реактивных графиков
4. **Tailwind**: Utility-first CSS с dark mode support

### Integration
1. **Token auto-refresh**: iiko (60 мин TTL), JWT (configurable)
2. **Retry logic**: tenacity с exponential backoff
3. **Graceful errors**: IikoAPIError с status_code

---

*Документ обновлён: 2026-02-01. Phase 3 завершена.*
