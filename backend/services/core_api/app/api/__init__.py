"""Core API — API Router aggregation.

All route modules are included here and mounted under their respective prefixes.
"""

from fastapi import APIRouter

from app.api.auth import router as auth_router
from app.api.services import router as services_router
from app.api.applications import router as applications_router
from app.api.documents import router as documents_router
from app.api.review import router as review_router
from app.api.assistant import router as assistant_router
from app.api.browser_sessions import router as browser_router
from app.api.tracking import router as tracking_router
from app.api.geo import router as geo_router

router = APIRouter()

router.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])
router.include_router(services_router, prefix="/api/v1/services", tags=["services"])
router.include_router(applications_router, prefix="/api/v1/applications", tags=["applications"])
router.include_router(documents_router, prefix="/api/v1", tags=["documents"])
router.include_router(review_router, prefix="/api/v1", tags=["review"])
router.include_router(assistant_router, prefix="/api/v1", tags=["assistant"])
router.include_router(browser_router, prefix="/api/v1", tags=["browser"])
router.include_router(tracking_router, prefix="/api/v1", tags=["tracking"])
router.include_router(geo_router, prefix="/api/v1/geo", tags=["geography"])
