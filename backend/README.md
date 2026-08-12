# Pharma App Backend

Production-oriented pharmaceutical operations backend built with FastAPI, SQLAlchemy 2.x, PostgreSQL/Supabase, Pydantic 2, Alembic, Typer, pytest, Ruff, and Pyright.

The uploaded architecture plan defines the core lifecycle as **Product → Production → Batch → QC → Inventory → Sales → Shipment/Export → Audit Trail**. The implementation keeps business rules in services/domain logic so API and CLI layers can share the same application behavior.

## Implemented backend capabilities

- Product catalog with activation/deactivation, search and pagination
- Production orders with validated lifecycle transitions
- Batch creation, unique batch numbers and QC/release workflow
- Transaction-based inventory movements and FEFO batch allocation
- Warehouses and authoritative multi-warehouse batch balances
- Batch-preserving stock transfers
- Customers and sales-order allocation with rollback-safe reservations
- Suppliers and raw-material records
- Pharmaceutical returns held for inspection/disposition
- Shipments and export orders with warehouse inventory reconciliation
- JWT authentication, Argon2 password hashing and RBAC
- Immutable-style audit records for important operations
- Inventory and audit reporting endpoints
- PostgreSQL/Supabase-ready migrations
- Non-root Docker runtime with HTTP healthcheck
- GitHub CI covering lint, type-checking, PostgreSQL migrations, tests, and container build

## API surface

All REST endpoints are under `/api/v1`.

- `GET /health` — liveness check
- `GET /ready` — readiness check with database connectivity
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
- `POST/GET /shipments` plus dispatch/delivery actions
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
6. Open `/docs` for generated OpenAPI documentation.
7. Run `ruff check src tests`, `pyright src tests`, and `pytest -q`.
8. Build the production image with `docker build -t pharma-management-api .`.

The container runs as an unprivileged user and exposes an HTTP healthcheck against `/api/v1/health`. Database migrations are intentionally run as a deployment step rather than implicitly during application startup.

Do not place Supabase service-role keys, database passwords, JWT secrets, or other credentials in source control.
