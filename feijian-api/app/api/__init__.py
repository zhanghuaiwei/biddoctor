from fastapi import APIRouter

from app.api import auth, billing, check, internal, projects, tasks

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(projects.router)
api_router.include_router(tasks.router)
api_router.include_router(check.router)
api_router.include_router(billing.router)
api_router.include_router(internal.router)
