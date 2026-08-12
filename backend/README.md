# Pharma App Backend

Production-oriented pharmaceutical operations backend built with FastAPI, SQLAlchemy 2.x, PostgreSQL/Supabase, Pydantic 2, Alembic, Typer, pytest, Ruff, and Pyright.

The uploaded architecture plan defines the core lifecycle as Product → Production → Batch → QC → Inventory → Sales → Shipment/Export → Audit Trail. This implementation keeps business rules in services/domain logic so the REST API and CLI can share the same application layer.

## Planned modules

- Products, formulations, raw materials, suppliers
- Production orders and batches
- QC and batch release
- Warehouses, inventory movements, FEFO allocation, transfers
- Customers, distributors, sales orders, invoices, returns
- Shipments and exports
- RBAC and permissions
- Audit logging and operational reporting

## Local development

1. Copy `.env.example` to `.env` and configure PostgreSQL/Supabase connection settings.
2. Install with `pip install -e .[dev]`.
3. Run `alembic upgrade head`.
4. Start the API with `uvicorn pharma_management.api.main:app --reload`.
5. Run tests with `pytest`.

Do not place Supabase service-role or database passwords in client-side code or source control.
