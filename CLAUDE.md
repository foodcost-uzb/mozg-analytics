# MOZG Analytics - BI Platform for Restaurant Business

## Project Overview

MOZG Analytics is a comprehensive BI analytics platform for the restaurant business, similar to MOZG REST. It provides real-time sales analytics, menu analysis, forecasting, and reporting capabilities.

## Architecture

```
├── backend/              # FastAPI Python backend
│   ├── app/
│   │   ├── api/v1/       # REST API endpoints
│   │   ├── core/         # Configuration, security, celery
│   │   ├── db/           # SQLAlchemy models, migrations
│   │   ├── integrations/ # iiko, rkeeper adapters
│   │   └── services/     # Business logic (reports, sync, analytics)
│   ├── alembic/          # Database migrations
│   └── tests/            # Pytest tests
├── frontend/             # Vue.js 3 dashboard (Phase 3)
├── telegram/             # Telegram bot + Mini App (Phase 6)
└── docker-compose.yml    # Infrastructure
```

## Technology Stack

- **Backend**: FastAPI, SQLAlchemy 2.0 (async), Alembic
- **Database**: PostgreSQL 15
- **Cache**: Redis 7
- **Task Queue**: Celery with Redis
- **Authentication**: JWT + Telegram OAuth
- **POS Integrations**: iiko Cloud API, R-Keeper (planned)
- **Analytics**: Pandas, NumPy
- **Forecasting**: Prophet, statsmodels (Phase 5)

## Database Schema

### Core Tables
- `organizations` - Multi-tenant organizations (restaurant groups)
- `users` - Users with role-based access (owner, admin, manager, analyst, viewer)
- `venues` - Individual restaurant venues with POS configuration

### POS Data
- `categories` - Menu categories from POS
- `products` - Menu items with prices
- `employees` - Staff members
- `receipts` - Sales transactions
- `receipt_items` - Individual items in receipts

### Aggregates
- `daily_sales` - Pre-computed daily metrics
- `hourly_sales` - Pre-computed hourly metrics

## Development Commands

```bash
# Backend development
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env

# Run migrations
alembic upgrade head

# Start API server
uvicorn app.main:app --reload --port 8000

# Run tests
pytest -v

# Start Celery worker
celery -A app.core.celery_app worker --loglevel=info

# Start Celery beat (scheduler)
celery -A app.core.celery_app beat --loglevel=info
```

```bash
# Docker development
docker-compose up -d           # Start all services
docker-compose logs -f api     # View API logs
docker-compose exec db psql -U mozg mozg_analytics  # DB shell
```

## API Endpoints

### Authentication
- `POST /api/v1/auth/register` - Register new organization + user
- `POST /api/v1/auth/login` - Email/password login
- `POST /api/v1/auth/telegram` - Telegram Mini App auth
- `POST /api/v1/auth/refresh` - Refresh access token
- `GET /api/v1/auth/me` - Get current user

### Organizations
- `GET /api/v1/organizations/current` - Get current organization
- `PATCH /api/v1/organizations/current` - Update organization
- `GET /api/v1/organizations/users` - List users
- `POST /api/v1/organizations/users` - Create user
- `PATCH /api/v1/organizations/users/{id}` - Update user
- `DELETE /api/v1/organizations/users/{id}` - Delete user

### Venues
- `GET /api/v1/venues` - List venues
- `POST /api/v1/venues` - Create venue
- `GET /api/v1/venues/{id}` - Get venue
- `PATCH /api/v1/venues/{id}` - Update venue
- `DELETE /api/v1/venues/{id}` - Delete venue
- `POST /api/v1/venues/{id}/sync` - Trigger data sync
- `GET /api/v1/venues/{id}/sync/status` - Get sync status

### Reports - Sales
- `GET /api/v1/reports/sales/summary` - Sales summary for period
- `GET /api/v1/reports/sales/daily` - Daily sales breakdown
- `GET /api/v1/reports/sales/comparison` - Compare with previous period
- `GET /api/v1/reports/sales/by-venue` - Sales by venue
- `GET /api/v1/reports/sales/hourly` - Hourly sales breakdown
- `GET /api/v1/reports/sales/plan-fact` - Plan vs actual comparison
- `GET /api/v1/reports/sales/top-days` - Top days by revenue
- `GET /api/v1/reports/sales/weekday-analysis` - Average by day of week

### Reports - Menu Analysis
- `GET /api/v1/reports/menu/abc` - ABC analysis (by revenue/profit/quantity)
- `GET /api/v1/reports/menu/margin` - Product margin analysis
- `GET /api/v1/reports/menu/go-list` - Go-List recommendations matrix
- `GET /api/v1/reports/menu/top-sellers` - Top selling products
- `GET /api/v1/reports/menu/worst-sellers` - Worst selling products
- `GET /api/v1/reports/menu/categories` - Category breakdown

### Export
- `GET /api/v1/reports/export/sales` - Export sales report to Excel
- `GET /api/v1/reports/export/abc` - Export ABC analysis to Excel
- `GET /api/v1/reports/export/go-list` - Export Go-List to Excel
- `GET /api/v1/reports/export/margin` - Export margin analysis to Excel

### Analytics - Motive Marketing
- `GET /api/v1/analytics/motive/report` - Full Motive Marketing report
- `GET /api/v1/analytics/motive/weekdays` - Weekday analysis
- `GET /api/v1/analytics/motive/seasonality` - Monthly seasonality

### Analytics - P&L
- `GET /api/v1/analytics/pnl/report` - Complete P&L report
- `GET /api/v1/analytics/pnl/margin-trend` - Monthly margin trend

### Analytics - HR
- `GET /api/v1/analytics/hr/report` - Complete HR analytics report
- `GET /api/v1/analytics/hr/rankings` - Employee rankings

### Analytics - Basket
- `GET /api/v1/analytics/basket/report` - Complete basket analysis
- `GET /api/v1/analytics/basket/product-pairs` - Product pairs (association rules)
- `GET /api/v1/analytics/basket/cross-sell` - Cross-sell recommendations

### Forecasting - Revenue
- `GET /api/v1/forecasting/revenue/forecast` - Prophet-based revenue forecast
- `GET /api/v1/forecasting/revenue/quick` - Quick forecast for dashboard

### Forecasting - Demand
- `GET /api/v1/forecasting/demand/forecast` - Product demand forecast
- `GET /api/v1/forecasting/demand/product/{id}` - Single product forecast

### Forecasting - Anomalies
- `GET /api/v1/forecasting/anomalies/report` - Full anomaly detection report
- `GET /api/v1/forecasting/anomalies/recent` - Recent anomalies for alerts

### Telegram Integration
- `POST /api/v1/telegram/webhook` - Telegram webhook handler
- `POST /api/v1/telegram/webhook/setup` - Set up webhook URL
- `DELETE /api/v1/telegram/webhook` - Remove webhook
- `POST /api/v1/telegram/link` - Link Telegram account via code
- `DELETE /api/v1/telegram/link` - Unlink Telegram account
- `GET /api/v1/telegram/notifications/settings` - Get notification settings
- `PATCH /api/v1/telegram/notifications/settings` - Update notification settings
- `GET /api/v1/telegram/bot/info` - Get bot information

## iiko Integration

The platform integrates with iiko Cloud API:
- Full and incremental data synchronization
- Menu/nomenclature sync (categories, products)
- Employees sync
- Sales data via OLAP reports
- Automatic scheduled sync via Celery

### Configuration
Set these in venue `pos_config`:
```json
{
  "organization_id": "iiko-org-uuid",
  "api_login": "your-api-login"
}
```

## Development Phases

### Phase 1: Foundation ✅
- Database schema with Alembic migrations
- FastAPI with JWT + Telegram auth
- CRUD for organizations, venues, users
- iiko sync service with Celery tasks

### Phase 2: Basic Reports ✅
- SalesReportService: summary, daily, hourly, comparison, by-venue
- MenuAnalysisService: ABC analysis, XYZ analysis, margin analysis
- Go-List matrix with recommendations (Stars, Workhorses, Puzzles, Dogs)
- Top/worst sellers, category analysis
- Excel export (openpyxl) for all reports
- Redis caching service
- Unit tests for report services

### Phase 3: Web Dashboard ✅
- Vue.js 3 + Vite + TypeScript
- Pinia stores (auth, venues, filters)
- Vue Router with auth guards
- Tailwind CSS styling
- ECharts visualizations (Line, Bar, Pie, Heatmap)
- Reusable components (StatCard, DataTable, DateRangePicker)
- Views: Dashboard, Sales, Menu (ABC/Go-List), Settings, Login

### Phase 4: Advanced Analytics ✅
- Motive Marketing analysis (weekday, seasonality, events, pricing)
- P&L report (revenue breakdown, COGS, margins, EBITDA)
- HR analytics (employee rankings, shifts, productivity)
- Basket analysis (product pairs, cross-sell, category affinity)

### Phase 5: Forecasting ✅
- RevenueForecastService: Prophet-based forecasting with seasonality
- DemandForecastService: Product demand prediction
- AnomalyDetectionService: Z-score based anomaly detection

### Phase 6: Telegram Integration ✅
- Extended bot commands (/start, /sales, /today, /week, /forecast, /alerts, /venues, /report, /settings, /link)
- Push notifications (morning/evening reports, anomaly alerts, goal achievements)
- Inline keyboards navigation
- Account linking via code

## Environment Variables

See `.env.example` for all configuration options:
- `DATABASE_URL` - PostgreSQL connection string
- `REDIS_URL` - Redis connection string
- `SECRET_KEY` - JWT signing key
- `TELEGRAM_BOT_TOKEN` - Telegram bot token
- `IIKO_API_LOGIN` - iiko API credentials

## Testing

```bash
# Create test database
createdb mozg_analytics_test

# Run tests
pytest -v

# With coverage
pytest --cov=app --cov-report=html
```

## Swagger Documentation

Access API docs at: http://localhost:8000/docs
