from fastapi import APIRouter

from app.api.v1 import (
    assets,
    audit,
    auth,
    dashboard,
    inventory,
    locations,
    notifications,
    procurements,
    reports,
    roles,
    suppliers,
    users,
    warehouses,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(roles.router)
api_router.include_router(locations.router)
api_router.include_router(warehouses.router)
api_router.include_router(assets.router)
api_router.include_router(suppliers.router)
api_router.include_router(procurements.router)
api_router.include_router(inventory.router)
api_router.include_router(notifications.router)
api_router.include_router(dashboard.router)
api_router.include_router(audit.router)
api_router.include_router(reports.router)
