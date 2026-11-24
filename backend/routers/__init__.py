"""
AquaPulse - Módulos de Routers FastAPI (P2.17)
"""
from backend.routers.auth import router as auth_router
from backend.routers.tanks import router as tanks_router
from backend.routers.measurements import router as measurements_router
from backend.routers.ai import router as ai_router
from backend.routers.maintenance import router as maintenance_router
from backend.routers.push import router as push_router
from backend.routers.admin import router as admin_router

__all__ = [
    "auth_router",
    "tanks_router",
    "measurements_router",
    "ai_router",
    "maintenance_router",
    "push_router",
    "admin_router",
]
