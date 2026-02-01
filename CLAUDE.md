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

### Phase 2: Basic Reports (Next)
- SalesReport: revenue by periods, comparisons
- MenuAnalysisReport: ABC analysis, margins
- Excel/PDF export
- Redis caching

### Phase 3: Web Dashboard
- Vue.js 3 + TypeScript
- Pinia state management
- ECharts visualizations

### Phase 4: Advanced Analytics
- Motive Marketing analysis
- P&L report
- HR analytics

### Phase 5: Forecasting
- Prophet revenue forecasting
- Demand prediction
- Anomaly detection

### Phase 6: Telegram Integration
- Extended bot commands
- Push notifications
- Mini App updates

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
