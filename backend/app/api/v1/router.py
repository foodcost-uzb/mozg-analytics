from fastapi import APIRouter

from app.api.v1 import auth, organizations, venues, reports, analytics, forecasting

api_router = APIRouter()

api_router.include_router(auth.router)
api_router.include_router(organizations.router)
api_router.include_router(venues.router)
api_router.include_router(reports.router)
api_router.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
api_router.include_router(forecasting.router, prefix="/forecasting", tags=["forecasting"])
