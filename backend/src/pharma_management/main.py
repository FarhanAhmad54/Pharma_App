from pharma_management.api import app
from pharma_management.operations_api import router as operations_router

app.include_router(operations_router, prefix="/api/v1")

__all__ = ["app"]
