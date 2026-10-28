from fastapi import APIRouter

from app.api import auth, billing, check, internal, projects, tasks, user_platform
from app.api.admin import admin_router

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(projects.router)
api_router.include_router(tasks.router)
api_router.include_router(check.router)
api_router.include_router(billing.router)
api_router.include_router(internal.router)
api_router.include_router(user_platform.router)
api_router.include_router(admin_router)
