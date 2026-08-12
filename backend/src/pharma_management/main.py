from pharma_management import api
from pharma_management.inventory_operations import complete_production, create_sale, transfer_stock
from pharma_management.shipping_api import router as shipping_router

# Use transactional multi-warehouse inventory operations before serving the app.
api.complete_production = complete_production
api.create_sale = create_sale
api.transfer_stock = transfer_stock

app = api.app
app.include_router(shipping_router)

__all__ = ["app"]
