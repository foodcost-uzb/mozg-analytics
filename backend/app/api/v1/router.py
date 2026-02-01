from fastapi import APIRouter

from app.api.v1 import auth, organizations, venues

api_router = APIRouter()

api_router.include_router(auth.router)
api_router.include_router(organizations.router)
api_router.include_router(venues.router)
