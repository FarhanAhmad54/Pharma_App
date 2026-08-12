# Pharma App Backend

Production-oriented pharmaceutical operations backend built with FastAPI, SQLAlchemy 2.x, PostgreSQL/Supabase, Pydantic 2, Alembic, Typer, pytest, Ruff, and Pyright.

The uploaded architecture plan defines the core lifecycle as **Product → Production → Batch → QC → Inventory → Sales → Shipment/Export → Audit Trail**. The implementation keeps business rules in services/domain logic so API and CLI layers can share the same application behavior.

## Implemented backend capabilities

- Product catalog with activation/deactivation, search and pagination
- Production orders with validated lifecycle transitions
- Batch creation, unique batch numbers and QC/release workflow
- Transaction-based inventory movements and FEFO batch allocation
- Warehouses and batch-preserving stock transfers
- Customers and sales-order allocation
- Suppliers and raw-material records
- Pharmaceutical returns held for inspection/disposition
- Shipments and export orders
- JWT authentication, Argon2 password hashing and RBAC
- Immutable-style audit records for important operations
- Inventory and audit reporting endpoints
- PostgreSQL/Supabase-ready migrations
- Docker image and GitHub CI for lint/test

## API surface

All REST endpoints are under `/api/v1`.

- `GET /health`
- `POST /auth/login`, `POST /auth/register`, `GET /auth/me`
- `GET/POST/PATCH /products`
- `GET/POST /warehouses`
- `GET/POST /production-orders` plus plan/approve/start/complete actions
- `GET /batches`, QC and release actions
- `POST/GET /customers`
- `POST/GET /sales`
- `POST/GET /suppliers`
- `POST/GET /raw-materials`
- `POST /returns`
- `POST/GET /shipments`
- `POST /exports`
- `POST /inventory/transfers`
- `GET /reports/inventory`
- `GET /audit-logs`

## Local development

1. Copy `.env.example` to `.env` and configure PostgreSQL/Supabase connection settings.
2. Install with `pip install -e '.[dev]'`.
3. Run `alembic upgrade head`.
4. Create the first super-admin with `python scripts/create_admin.py`.
5. Start the API with `uvicorn pharma_management.main:app --reload`.
6. Open `/docs` for the generated OpenAPI documentation.
7. Run `ruff check src tests` and `pytest -q`.

Do not place Supabase service-role keys, database passwords, JWT secrets, or other credentials in source control.
