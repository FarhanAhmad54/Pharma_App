from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.orm import Session

from pharma_management.config import get_settings
from pharma_management.db import get_db
from pharma_management.models import Batch, Customer, Product, ProductionOrder, ProductionStatus, QCStatus, User, UserRole, Warehouse
from pharma_management.schemas import (
    BatchOut, CompleteProductionRequest, LoginRequest, ProductCreate, ProductOut, ProductUpdate,
    ProductionCreate, ProductionOut, QCRequest, SaleCreate, SaleOut, TokenOut, TransferRequest,
    UserCreate, UserOut, WarehouseCreate, WarehouseOut,
)
from pharma_management.security import create_access_token, current_user, hash_password, require_roles, verify_password
from pharma_management.services import complete_production, create_product, create_production, create_sale, record_qc, release_batch, transfer_stock, transition_production, update_product

settings = get_settings()
app = FastAPI(title=settings.app_name, version="0.1.0", docs_url="/docs", redoc_url="/redoc")
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
router = APIRouter(prefix="/api/v1")


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "pharma-management-api"}


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
def login(data: LoginRequest, db: Session = Depends(get_db)) -> TokenOut:
    user = db.scalar(select(User).where(User.email == data.email))
    if not user or not user.active or not verify_password(data.password, user.password_hash):
        raise HTTPException(401, "Invalid email or password")
    token, expires = create_access_token(user)
    return TokenOut(access_token=token, expires_in=expires, user=user)


@router.get("/auth/me", response_model=UserOut)
def me(user: User = Depends(current_user)) -> User:
    return user


@router.post("/products", response_model=ProductOut, status_code=201, dependencies=[Depends(require_roles(UserRole.ADMIN, UserRole.INVENTORY_MANAGER))])
def product_create(data: ProductCreate, db: Session = Depends(get_db), user: User = Depends(current_user)) -> Product:
    return create_product(db, data, user)


@router.get("/products", response_model=list[ProductOut])
def products(search: str | None = Query(default=None), active: bool | None = None, limit: int = Query(default=50, ge=1, le=200), offset: int = Query(default=0, ge=0), db: Session = Depends(get_db), _: User = Depends(current_user)) -> list[Product]:
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
    return create_production(db, data, user)


@router.get("/production-orders", response_model=list[ProductionOut])
def production_list(status: ProductionStatus | None = None, db: Session = Depends(get_db), _: User = Depends(current_user)) -> list[ProductionOrder]:
    query = select(ProductionOrder).order_by(ProductionOrder.created_at.desc())
    if status:
        query = query.where(ProductionOrder.status == status)
    return list(db.scalars(query))


def production_transition(target: ProductionStatus):
    def endpoint(order_id: UUID, db: Session = Depends(get_db), user: User = Depends(current_user)) -> ProductionOut:
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
def batches(status: str | None = None, product_id: UUID | None = None, db: Session = Depends(get_db), _: User = Depends(current_user)) -> list[Batch]:
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


@router.post("/customers", status_code=201, dependencies=[Depends(require_roles(UserRole.ADMIN, UserRole.SALES_MANAGER))])
def customer_create(data: dict, db: Session = Depends(get_db)) -> dict:
    required = {"name", "code"}
    if not required.issubset(data):
        raise HTTPException(422, "name and code are required")
    if db.scalar(select(Customer).where(Customer.code == data["code"])):
        raise HTTPException(409, "Customer code already exists")
    customer = Customer(**{key: data[key] for key in ("name", "code", "email", "phone", "address") if key in data})
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return {"id": str(customer.id), "name": customer.name, "code": customer.code, "active": customer.active}


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
