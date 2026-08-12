from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from sqlalchemy import select
from sqlalchemy.orm import Session

from pharma_management.auth_models import AuthSession
from pharma_management.config import get_settings
from pharma_management.db import get_db
from pharma_management.inventory_operations import complete_production, create_sale, transfer_stock
from pharma_management.models import (
    Batch,
    Customer,
    Product,
    ProductionOrder,
    ProductionStatus,
    SalesOrder,
    User,
    UserRole,
    Warehouse,
)
from pharma_management.observability import RequestContextMiddleware, install_exception_handlers
from pharma_management.schemas import (
    BatchOut,
    CompleteProductionRequest,
    CustomerCreate,
    CustomerOut,
    LoginRequest,
    ProductCreate,
    ProductOut,
    ProductUpdate,
    ProductionCreate,
    ProductionOut,
    QCRequest,
    SaleCreate,
    SaleOut,
    TokenOut,
    TransferRequest,
    UserCreate,
    UserOut,
    WarehouseCreate,
    WarehouseOut,
)
from pharma_management.security import (
    authenticate_user,
    create_access_token,
    create_session,
    current_user,
    hash_password,
    require_roles,
    revoke_session,
)
from pharma_management.services import record_qc, release_batch, transition_production, update_product

settings = get_settings()
docs_enabled = settings.enable_docs and settings.environment != "production"
app = FastAPI(title=settings.app_name, version=settings.app_version, docs_url="/docs" if docs_enabled else None, redoc_url="/redoc" if docs_enabled else None)
app.add_middleware(RequestContextMiddleware)
if settings.trusted_hosts != ["*"]:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.trusted_hosts)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=True, allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"], allow_headers=["Authorization", "Content-Type", "X-Request-ID"])


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    if settings.security_headers:
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        response.headers.setdefault("Cache-Control", "no-store" if request.url.path.startswith("/api/") else "no-cache")
        if settings.environment == "production":
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response


install_exception_handlers(app)
router = APIRouter(prefix="/api/v1")


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "pharma-management-api", "version": settings.app_version}


@router.post("/auth/register", response_model=UserOut, dependencies=[Depends(require_roles(UserRole.SUPER_ADMIN))])
def register(data: UserCreate, db: Session = Depends(get_db)) -> User:
    if db.scalar(select(User).where(User.email == data.email)):
        raise HTTPException(409, "Email already registered")
    user = User(email=data.email, full_name=data.full_name, password_hash=hash_password(data.password), role=data.role)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/auth/login", response_model=TokenOut)
def login(data: LoginRequest, request: Request, db: Session = Depends(get_db)) -> TokenOut:
    user = authenticate_user(db, str(data.email), data.password)
    if user is None:
        raise HTTPException(401, "Invalid email or password")
    token, expires, jti = create_access_token(user)
    create_session(db, user, jti, datetime.now(UTC) + timedelta(seconds=expires), request)
    return TokenOut(access_token=token, expires_in=expires, user=UserOut.model_validate(user))


@router.post("/auth/logout", status_code=204)
def logout(request: Request, db: Session = Depends(get_db), _user: User = Depends(current_user)) -> None:
    auth = request.headers.get("Authorization", "")
    token = auth[7:] if auth.lower().startswith("bearer ") else ""
    if token:
        revoke_session(db, token)


@router.get("/auth/sessions")
def sessions(db: Session = Depends(get_db), user: User = Depends(current_user)) -> list[dict[str, Any]]:
    rows = db.scalars(select(AuthSession).where(AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None), AuthSession.expires_at > datetime.now(UTC)).order_by(AuthSession.created_at.desc())).all()
    return [{"id": str(row.id), "created_at": row.created_at, "expires_at": row.expires_at, "ip_address": row.ip_address, "user_agent": row.user_agent} for row in rows]


@router.delete("/auth/sessions/{session_id}", status_code=204)
def revoke_session_by_id(session_id: UUID, db: Session = Depends(get_db), user: User = Depends(current_user)) -> None:
    session = db.scalar(select(AuthSession).where(AuthSession.id == session_id, AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None)))
    if not session:
        raise HTTPException(404, "Session not found")
    session.revoked_at = datetime.now(UTC)
    db.commit()


@router.delete("/auth/sessions", status_code=204)
def revoke_all_sessions(db: Session = Depends(get_db), user: User = Depends(current_user)) -> None:
    now = datetime.now(UTC)
    rows = db.scalars(select(AuthSession).where(AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None))).all()
    for session in rows:
        session.revoked_at = now
    db.commit()


@router.get("/auth/me", response_model=UserOut)
def me(user: User = Depends(current_user)) -> User:
    return user


@router.post("/products", response_model=ProductOut, status_code=201, dependencies=[Depends(require_roles(UserRole.ADMIN, UserRole.INVENTORY_MANAGER))])
def product_create(data: ProductCreate, db: Session = Depends(get_db), user: User = Depends(current_user)) -> Product:
    from pharma_management.services import create_product
    return create_product(db, data, user)


@router.get("/products", response_model=list[ProductOut])
def products(search: str | None = Query(default=None, max_length=100), active: bool | None = None, limit: int = Query(default=50, ge=1, le=200), offset: int = Query(default=0, ge=0), db: Session = Depends(get_db), _: User = Depends(current_user)) -> list[Product]:
    query = select(Product).order_by(Product.created_at.desc()).offset(offset).limit(limit)
    if active is not None:
        query = query.where(Product.active == active)
    if search:
        pattern = f"%{search}%"
        query = query.where(Product.sku.ilike(pattern) | Product.brand_name.ilike(pattern) | Product.generic_name.ilike(pattern))
    return list(db.scalars(query))


@router.get("/products/{product_id}", response_model=ProductOut)
def product_get(product_id: UUID, db: Session = Depends(get_db), _: User = Depends(current_user)) -> Product:
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(404, "Product not found")
    return product


@router.patch("/products/{product_id}", response_model=ProductOut, dependencies=[Depends(require_roles(UserRole.ADMIN, UserRole.INVENTORY_MANAGER))])
def product_update(product_id: UUID, data: ProductUpdate, db: Session = Depends(get_db), user: User = Depends(current_user)) -> Product:
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(404, "Product not found")
    return update_product(db, product, data, user)


@router.post("/warehouses", response_model=WarehouseOut, status_code=201, dependencies=[Depends(require_roles(UserRole.ADMIN, UserRole.WAREHOUSE_MANAGER))])
def warehouse_create(data: WarehouseCreate, db: Session = Depends(get_db)) -> Warehouse:
    if db.scalar(select(Warehouse).where(Warehouse.code == data.code)):
        raise HTTPException(409, "Warehouse code already exists")
    warehouse = Warehouse(**data.model_dump())
    db.add(warehouse)
    db.commit()
    db.refresh(warehouse)
    return warehouse


@router.get("/warehouses", response_model=list[WarehouseOut])
def warehouses(db: Session = Depends(get_db), _: User = Depends(current_user)) -> list[Warehouse]:
    return list(db.scalars(select(Warehouse).order_by(Warehouse.code)))


@router.post("/production-orders", response_model=ProductionOut, status_code=201, dependencies=[Depends(require_roles(UserRole.ADMIN, UserRole.PRODUCTION_MANAGER))])
def production_create(data: ProductionCreate, db: Session = Depends(get_db), user: User = Depends(current_user)) -> ProductionOrder:
    from pharma_management.services import create_production
    return create_production(db, data, user)


@router.get("/production-orders", response_model=list[ProductionOut])
def production_list(status: ProductionStatus | None = None, db: Session = Depends(get_db), _: User = Depends(current_user)) -> list[ProductionOrder]:
    query = select(ProductionOrder).order_by(ProductionOrder.created_at.desc())
    if status:
        query = query.where(ProductionOrder.status == status)
    return list(db.scalars(query))


def production_transition(target: ProductionStatus):
    def endpoint(order_id: UUID, db: Session = Depends(get_db), user: User = Depends(current_user)) -> Any:
        order = db.get(ProductionOrder, order_id)
        if not order:
            raise HTTPException(404, "Production order not found")
        return transition_production(db, order, target, user)
    return endpoint


router.post("/production-orders/{order_id}/plan", response_model=ProductionOut, dependencies=[Depends(require_roles(UserRole.ADMIN, UserRole.PRODUCTION_MANAGER))])(production_transition(ProductionStatus.PLANNED))
router.post("/production-orders/{order_id}/approve", response_model=ProductionOut, dependencies=[Depends(require_roles(UserRole.ADMIN, UserRole.PRODUCTION_MANAGER))])(production_transition(ProductionStatus.APPROVED))
router.post("/production-orders/{order_id}/start", response_model=ProductionOut, dependencies=[Depends(require_roles(UserRole.ADMIN, UserRole.PRODUCTION_MANAGER))])(production_transition(ProductionStatus.IN_PROGRESS))


@router.post("/production-orders/{order_id}/complete", response_model=BatchOut, dependencies=[Depends(require_roles(UserRole.ADMIN, UserRole.PRODUCTION_MANAGER))])
def production_complete(order_id: UUID, data: CompleteProductionRequest, db: Session = Depends(get_db), user: User = Depends(current_user)) -> Batch:
    order = db.get(ProductionOrder, order_id)
    if not order:
        raise HTTPException(404, "Production order not found")
    return complete_production(db, order, data, user)


@router.get("/batches", response_model=list[BatchOut])
def batches(status: str | None = Query(default=None, max_length=40), product_id: UUID | None = None, db: Session = Depends(get_db), _: User = Depends(current_user)) -> list[Batch]:
    query = select(Batch).order_by(Batch.expiry_date.asc())
    if status:
        query = query.where(Batch.status == status)
    if product_id:
        query = query.where(Batch.product_id == product_id)
    return list(db.scalars(query))


@router.get("/batches/{batch_id}", response_model=BatchOut)
def batch_get(batch_id: UUID, db: Session = Depends(get_db), _: User = Depends(current_user)) -> Batch:
    batch = db.get(Batch, batch_id)
    if not batch:
        raise HTTPException(404, "Batch not found")
    return batch


@router.post("/batches/{batch_id}/qc", response_model=BatchOut, dependencies=[Depends(require_roles(UserRole.ADMIN, UserRole.QUALITY_MANAGER))])
def batch_qc(batch_id: UUID, data: QCRequest, db: Session = Depends(get_db), user: User = Depends(current_user)) -> Batch:
    batch = db.get(Batch, batch_id)
    if not batch:
        raise HTTPException(404, "Batch not found")
    return record_qc(db, batch, data, user)


@router.post("/batches/{batch_id}/release", response_model=BatchOut, dependencies=[Depends(require_roles(UserRole.ADMIN, UserRole.QUALITY_MANAGER))])
def batch_release(batch_id: UUID, db: Session = Depends(get_db), user: User = Depends(current_user)) -> Batch:
    batch = db.get(Batch, batch_id)
    if not batch:
        raise HTTPException(404, "Batch not found")
    return release_batch(db, batch, user)


@router.post("/customers", response_model=CustomerOut, status_code=201, dependencies=[Depends(require_roles(UserRole.ADMIN, UserRole.SALES_MANAGER))])
def customer_create(data: CustomerCreate, db: Session = Depends(get_db)) -> Customer:
    if db.scalar(select(Customer).where(Customer.code == data.code)):
        raise HTTPException(409, "Customer code already exists")
    customer = Customer(**data.model_dump())
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer


@router.get("/customers/{customer_id}", response_model=CustomerOut)
def customer_get(customer_id: UUID, db: Session = Depends(get_db), _: User = Depends(current_user)) -> Customer:
    customer = db.get(Customer, customer_id)
    if not customer:
        raise HTTPException(404, "Customer not found")
    return customer


@router.post("/sales", response_model=SaleOut, status_code=201, dependencies=[Depends(require_roles(UserRole.ADMIN, UserRole.SALES_MANAGER))])
def sale_create(data: SaleCreate, warehouse_id: UUID = Query(...), db: Session = Depends(get_db), user: User = Depends(current_user)) -> SalesOrder:
    return create_sale(db, data, warehouse_id, user)


@router.get("/sales", response_model=list[SaleOut])
def sales(db: Session = Depends(get_db), _: User = Depends(current_user)) -> list[SalesOrder]:
    return list(db.scalars(select(SalesOrder).order_by(SalesOrder.created_at.desc()).limit(200)))


@router.post("/inventory/transfers", status_code=204, dependencies=[Depends(require_roles(UserRole.ADMIN, UserRole.WAREHOUSE_MANAGER, UserRole.INVENTORY_MANAGER))])
def inventory_transfer(data: TransferRequest, db: Session = Depends(get_db), user: User = Depends(current_user)) -> None:
    transfer_stock(db, data, user)


app.include_router(router)
