from fastapi import APIRouter

from app.api.v1 import health, intelligence, overview

router = APIRouter()
router.include_router(health.router)
router.include_router(overview.router)
router.include_router(intelligence.router)
