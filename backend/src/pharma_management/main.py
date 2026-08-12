from pharma_management import api
from pharma_management.inventory_operations import complete_production, create_sale, transfer_stock
from pharma_management.operations_api import router as operations_router
from pharma_management.readiness import router as readiness_router
from pharma_management.shipping_api import router as shipping_router
from pharma_management.support_api import router as support_router

# Serve the transactional inventory, operational modules, readiness, shipment lifecycle, and commercial history lookups.
api.complete_production = complete_production
api.create_sale = create_sale
api.transfer_stock = transfer_stock

app = api.app
app.include_router(operations_router)
app.include_router(readiness_router)
app.include_router(shipping_router)
app.include_router(support_router)

__all__ = ["app"]
