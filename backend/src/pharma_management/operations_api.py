from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pharma_management.db import get_db
from pharma_management.extended_models import RawMaterial, ReturnOrder, Supplier
from pharma_management.models import AuditLog, Batch, Customer, ExportOrder, InventoryMovement, MovementType, Shipment, ShipmentStatus, User, UserRole
from pharma_management.security import current_user, require_roles

router = APIRouter()


class SupplierCreate(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=180)
    contact_name: str | None = None
    email: str | None = None
    phone: str | None = None
    address: str | None = None


class RawMaterialCreate(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=180)
    material_type: str = Field(min_length=1, max_length=80)
    unit: str = Field(min_length=1, max_length=32)
    supplier_id: UUID | None = None
    quantity: Decimal = Field(default=Decimal("0"), ge=0)
    minimum_stock: Decimal = Field(default=Decimal("0"), ge=0)
    storage_requirements: str | None = None
    lot_number: str | None = None
    expiry_date: date | None = None


class ReturnCreate(BaseModel):
    sales_order_id: UUID
    customer_id: UUID
    product_id: UUID
    batch_id: UUID
    quantity: Decimal = Field(gt=0)
    reason: str = Field(min_length=1)
    return_condition: str = Field(min_length=1)
    inspection_result: str | None = None
    disposition: str = "QUARANTINE"


class ShipmentCreate(BaseModel):
    sales_order_id: UUID | None = None
    destination: str = Field(min_length=1)
    carrier: str | None = None
    tracking_number: str | None = None
    status: ShipmentStatus = ShipmentStatus.PREPARING
    dispatch_date: date | None = None


class ExportCreate(BaseModel):
    reference_number: str = Field(min_length=1, max_length=80)
    destination_country: str = Field(min_length=2, max_length=2)
    importer: str = Field(min_length=1, max_length=180)
    product_id: UUID
    batch_id: UUID
    quantity: Decimal = Field(gt=0)
    currency: str = Field(min_length=3, max_length=3)
    export_value: Decimal = Field(ge=0)
    shipment_id: UUID | None = None
    export_date: date | None = None


@router.post("/suppliers", status_code=201, dependencies=[Depends(require_roles(UserRole.ADMIN, UserRole.INVENTORY_MANAGER))])
def create_supplier(data: SupplierCreate, db: Session = Depends(get_db)) -> Supplier:
    if db.scalar(select(Supplier).where(Supplier.code == data.code)):
        raise HTTPException(409, "Supplier code already exists")
    supplier = Supplier(**data.model_dump())
    db.add(supplier)
    db.commit()
    db.refresh(supplier)
    return supplier


@router.get("/suppliers")
def list_suppliers(db: Session = Depends(get_db), _: User = Depends(current_user)) -> list[Supplier]:
    return list(db.scalars(select(Supplier).order_by(Supplier.name)))


@router.post("/raw-materials", status_code=201, dependencies=[Depends(require_roles(UserRole.ADMIN, UserRole.INVENTORY_MANAGER))])
def create_raw_material(data: RawMaterialCreate, db: Session = Depends(get_db)) -> RawMaterial:
    if db.scalar(select(RawMaterial).where(RawMaterial.code == data.code)):
        raise HTTPException(409, "Raw material code already exists")
    if data.supplier_id and not db.get(Supplier, data.supplier_id):
        raise HTTPException(404, "Supplier not found")
    material = RawMaterial(**data.model_dump())
    db.add(material)
    db.commit()
    db.refresh(material)
    return material


@router.get("/raw-materials")
def list_raw_materials(db: Session = Depends(get_db), _: User = Depends(current_user)) -> list[RawMaterial]:
    return list(db.scalars(select(RawMaterial).order_by(RawMaterial.name)))


@router.post("/returns", status_code=201, dependencies=[Depends(require_roles(UserRole.ADMIN, UserRole.SALES_MANAGER, UserRole.QUALITY_MANAGER))])
def create_return(data: ReturnCreate, db: Session = Depends(get_db), user: User = Depends(current_user)) -> ReturnOrder:
    if not db.get(Customer, data.customer_id) or not db.get(Batch, data.batch_id):
        raise HTTPException(404, "Customer or batch not found")
    batch = db.scalar(select(Batch).where(Batch.id == data.batch_id).with_for_update())
    if not batch or batch.product_id != data.product_id:
        raise HTTPException(409, "Returned batch does not match product")
    if data.quantity > batch.quantity_sold:
        raise HTTPException(409, "Return quantity exceeds quantity sold from batch")
    result = ReturnOrder(**data.model_dump())
    db.add(result)
    db.add(InventoryMovement(product_id=data.product_id, batch_id=data.batch_id, warehouse_id=batch.warehouse_id, quantity=Decimal("0"), movement_type=MovementType.RETURN, user_id=user.id, reason="Return received; held for inspection"))
    db.commit()
    db.refresh(result)
    return result


@router.post("/shipments", status_code=201, dependencies=[Depends(require_roles(UserRole.ADMIN, UserRole.WAREHOUSE_MANAGER, UserRole.SALES_MANAGER))])
def create_shipment(data: ShipmentCreate, db: Session = Depends(get_db)) -> Shipment:
    if data.tracking_number and db.scalar(select(Shipment).where(Shipment.tracking_number == data.tracking_number)):
        raise HTTPException(409, "Tracking number already exists")
    shipment = Shipment(**data.model_dump())
    db.add(shipment)
    db.commit()
    db.refresh(shipment)
    return shipment


@router.get("/shipments")
def list_shipments(db: Session = Depends(get_db), _: User = Depends(current_user)) -> list[Shipment]:
    return list(db.scalars(select(Shipment).order_by(Shipment.id.desc()).limit(200)))


@router.post("/exports", status_code=201, dependencies=[Depends(require_roles(UserRole.ADMIN, UserRole.SALES_MANAGER))])
def create_export(data: ExportCreate, db: Session = Depends(get_db)) -> ExportOrder:
    if db.scalar(select(ExportOrder).where(ExportOrder.reference_number == data.reference_number)):
        raise HTTPException(409, "Export reference already exists")
    batch = db.get(Batch, data.batch_id)
    if not batch or batch.product_id != data.product_id:
        raise HTTPException(404, "Batch/product not found")
    if batch.status.value != "RELEASED" or batch.expiry_date <= date.today():
        raise HTTPException(409, "Export batch is not eligible")
    if batch.quantity_available < data.quantity:
        raise HTTPException(409, "Insufficient batch quantity")
    export = ExportOrder(**data.model_dump(), destination_country=data.destination_country.upper(), currency=data.currency.upper(), status="CONFIRMED")
    batch.quantity_available -= data.quantity
    db.add(export)
    db.add(InventoryMovement(product_id=data.product_id, batch_id=data.batch_id, warehouse_id=batch.warehouse_id, quantity=-data.quantity, movement_type=MovementType.SALE, reference_document=data.reference_number, reason="Export allocation"))
    db.commit()
    db.refresh(export)
    return export


@router.get("/reports/inventory")
def inventory_report(db: Session = Depends(get_db), _: User = Depends(current_user)) -> list[dict]:
    rows = db.execute(select(InventoryMovement.product_id, InventoryMovement.warehouse_id, func.sum(InventoryMovement.quantity).label("net_quantity")).group_by(InventoryMovement.product_id, InventoryMovement.warehouse_id)).all()
    return [{"product_id": str(row.product_id), "warehouse_id": str(row.warehouse_id), "net_quantity": str(row.net_quantity or 0)} for row in rows]


@router.get("/audit-logs")
def audit_logs(limit: int = 100, db: Session = Depends(get_db), _: User = Depends(require_roles(UserRole.ADMIN, UserRole.AUDITOR, UserRole.SUPER_ADMIN))) -> list[AuditLog]:
    return list(db.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(min(limit, 500))))
