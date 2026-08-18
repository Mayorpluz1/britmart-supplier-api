"""Central router for version 1 of the BritMart API."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.v1.purchase_orders import (
    router as purchase_orders_router,
)
from app.api.v1.shipments import router as shipments_router
from app.api.v1.supplier_performance import (
    router as supplier_performance_router,
)
from app.api.v1.suppliers import router as suppliers_router
from app.core.failure_simulation import (
    simulate_controlled_failure,
)


api_v1_router = APIRouter()

simulation_dependency = Depends(
    simulate_controlled_failure
)

api_v1_router.include_router(
    suppliers_router,
    dependencies=[simulation_dependency],
)

api_v1_router.include_router(
    purchase_orders_router,
    dependencies=[simulation_dependency],
)

api_v1_router.include_router(
    shipments_router,
    dependencies=[simulation_dependency],
)

api_v1_router.include_router(
    supplier_performance_router,
    dependencies=[simulation_dependency],
)