from pharma_management import api
from pharma_management.inventory_operations import complete_production, create_sale, transfer_stock

# Replace legacy single-warehouse implementations with the transactional,
# warehouse-specific inventory operations before the application is served.
api.complete_production = complete_production
api.create_sale = create_sale
api.transfer_stock = transfer_stock

app = api.app

__all__ = ["app"]
