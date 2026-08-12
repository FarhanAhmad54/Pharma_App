from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pharma_management.db import get_db
from pharma_management.extended_models import RawMaterial, ReturnOrder, Supplier
from pharma_management.inventory_models import BatchInventory
from pharma_management.models import (
    AuditLog,
    Batch,
    BatchAllocation,
    BatchStatus,
    Customer,
    ExportOrder,
    InventoryMovement,
    Invoice,
    MovementType,
    OrderStatus,
    SalesItem,
    SalesOrder,
    Shipment,
    ShipmentStatus,
    User,
    UserRole,
    Warehouse,
)
from pharma_management.security import current_user, require_roles

router = APIRouter()


def orm_dict(obj: Any) -> dict[str, Any]:
    return {column.name: getattr(obj, column.name) for column in obj.__table__.columns}


class SupplierCreate(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=180)
    contact_name: str | None = Field(default=None, max_length=160)
    email: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=40)
    address: str | None = Field(default=None, max_length=4000)


class RawMaterialCreate(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=180)
    material_type: str = Field(min_length=1, max_length=80)
    unit: str = Field(min_length=1, max_length=32)
    supplier_id: UUID | None = None
    quantity: Decimal = Field(default=Decimal("0"), ge=0)
    minimum_stock: Decimal = Field(default=Decimal("0"), ge=0)
    storage_requirements: str | None = Field(default=None, max_length=4000)
    lot_number: str | None = Field(default=None, max_length=80)
    expiry_date: date | None = None


class ReturnCreate(BaseModel):
    return_number: str = Field(min_length=1, max_length=80)
    invoice_id: UUID
    customer_id: UUID
    product_id: UUID
    batch_id: UUID
    quantity: Decimal = Field(gt=0)
    reason: str = Field(min_length=1, max_length=2000)
    return_condition: str | None = Field(default=None, max_length=80)
    inspection_result: str | None = Field(default=None, max_length=255)
    disposition: str | None = Field(default="QUARANTINE", max_length=80)


class ShipmentCreate(BaseModel):
    shipment_number: str | None = Field(default=None, max_length=80)
    sales_order_id: UUID | None = None
    destination: str = Field(min_length=1, max_length=4000)
    carrier: str | None = Field(default=None, max_length=120)
    tracking_number: str | None = Field(default=None, max_length=120)
    status: ShipmentStatus = ShipmentStatus.PREPARING
    dispatch_date: datetime | None = None

    @field_validator("status", "dispatch_date")
    @classmethod
    def validate_initial_state(cls, value: Any, info) -> Any:
        if info.field_name == "status" and value not in {ShipmentStatus.PREPARING, ShipmentStatus.READY}:
            raise ValueError("New shipments must start in PREPARING or READY state")
        if info.field_name == "dispatch_date" and value is not None:
            raise ValueError("dispatch_date is assigned by the dispatch workflow")
        return value


class ExportCreate(BaseModel):
    export_number: str = Field(min_length=1, max_length=80)
    destination_country: str = Field(min_length=2, max_length=2)
    importer: str = Field(min_length=1, max_length=180)
    product_id: UUID
    batch_id: UUID
    warehouse_id: UUID
    quantity: Decimal = Field(gt=0)
    currency: str = Field(min_length=3, max_length=3)
    export_value: Decimal = Field(ge=0)
    shipment_id: UUID | None = None
    export_date: date | None = None
    reference_document: str | None = Field(default=None, max_length=4000)

    @field_validator("destination_country", "currency")
    @classmethod
    def normalize_code(cls, value: str, info) -> str:
        normalized = value.upper()
        expected = 2 if info.field_name == "destination_country" else 3
        if len(normalized) != expected or not normalized.isalpha():
            raise ValueError(f"{info.field_name} must be alphabetic with length {expected}")
        return normalized


@router.post("/suppliers", status_code=201, dependencies=[Depends(require_roles(UserRole.ADMIN, UserRole.INVENTORY_MANAGER))])
def create_supplier(data: SupplierCreate, db: Session = Depends(get_db)) -> dict[str, Any]:
    if db.scalar(select(Supplier).where(Supplier.code == data.code)):
        raise HTTPException(409, "Supplier code already exists")
    supplier = Supplier(**data.model_dump())
    db.add(supplier)
    db.commit()
    db.refresh(supplier)
    return orm_dict(supplier)


@router.get("/suppliers")
def list_suppliers(db: Session = Depends(get_db), _: User = Depends(current_user)) -> list[dict[str, Any]]:
    return [orm_dict(item) for item in db.scalars(select(Supplier).order_by(Supplier.name))]


@router.post("/raw-materials", status_code=201, dependencies=[Depends(require_roles(UserRole.ADMIN, UserRole.INVENTORY_MANAGER))])
def create_raw_material(data: RawMaterialCreate, db: Session = Depends(get_db)) -> dict[str, Any]:
    if db.scalar(select(RawMaterial).where(RawMaterial.code == data.code)):
        raise HTTPException(409, "Raw material code already exists")
    if data.supplier_id and not db.get(Supplier, data.supplier_id):
        raise HTTPException(404, "Supplier not found")
    material = RawMaterial(**data.model_dump())
    db.add(material)
    db.commit()
    db.refresh(material)
    return orm_dict(material)


@router.get("/raw-materials")
def list_raw_materials(db: Session = Depends(get_db), _: User = Depends(current_user)) -> list[dict[str, Any]]:
    return [orm_dict(item) for item in db.scalars(select(RawMaterial).order_by(RawMaterial.name))]


@router.post("/returns", status_code=201, dependencies=[Depends(require_roles(UserRole.ADMIN, UserRole.SALES_MANAGER, UserRole.QUALITY_MANAGER))])
def create_return(data: ReturnCreate, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    if db.scalar(select(ReturnOrder).where(ReturnOrder.return_number == data.return_number)):
        raise HTTPException(409, "Return number already exists")
    customer = db.get(Customer, data.customer_id)
    invoice = db.get(Invoice, data.invoice_id)
    if not customer or not customer.active:
        raise HTTPException(404, "Customer not found or inactive")
    if not invoice:
        raise HTTPException(404, "Invoice not found")
    order = db.get(SalesOrder, invoice.sales_order_id)
    if not order or order.customer_id != data.customer_id:
        raise HTTPException(409, "Invoice does not belong to the supplied customer")
    item = db.scalar(select(SalesItem).where(SalesItem.sales_order_id == order.id, SalesItem.product_id == data.product_id))
    if not item:
        raise HTTPException(409, "Returned product was not part of the invoiced order")
    batch = db.scalar(select(Batch).where(Batch.id == data.batch_id).with_for_update())
    if not batch or batch.product_id != data.product_id:
        raise HTTPException(409, "Returned batch does not match product")

    allocated_to_invoice = db.scalar(
        select(func.coalesce(func.sum(BatchAllocation.quantity), 0))
        .join(SalesItem, SalesItem.id == BatchAllocation.sales_item_id)
        .where(SalesItem.sales_order_id == order.id, SalesItem.product_id == data.product_id, BatchAllocation.batch_id == data.batch_id)
    ) or Decimal("0")
    returned = db.scalar(
        select(func.coalesce(func.sum(ReturnOrder.quantity), 0)).where(
            ReturnOrder.invoice_id == data.invoice_id,
            ReturnOrder.product_id == data.product_id,
            ReturnOrder.batch_id == data.batch_id,
        )
    ) or Decimal("0")
    if allocated_to_invoice <= 0:
        raise HTTPException(409, "Returned batch was not allocated to this invoice")
    if returned + data.quantity > allocated_to_invoice:
        raise HTTPException(409, "Return quantity exceeds the remaining quantity allocated to this invoice and batch")

    result = ReturnOrder(**data.model_dump(), created_by=user.id)
    db.add(result)
    db.flush()
    db.add(AuditLog(user_id=user.id, action="RETURN_RECEIVED", entity="Return", entity_type="Return", entity_id=str(result.id), reason="Return received; held for inspection"))
    db.commit()
    db.refresh(result)
    return orm_dict(result)


@router.post("/shipments", status_code=201, dependencies=[Depends(require_roles(UserRole.ADMIN, UserRole.WAREHOUSE_MANAGER, UserRole.SALES_MANAGER))])
def create_shipment(data: ShipmentCreate, db: Session = Depends(get_db)) -> dict[str, Any]:
    shipment_number = data.shipment_number or f"SHP-{datetime.now(timezone.utc):%Y%m%d%H%M%S}-{uuid4().hex[:8].upper()}"
    if db.scalar(select(Shipment).where(Shipment.shipment_number == shipment_number)):
        raise HTTPException(409, "Shipment number already exists")
    if data.sales_order_id:
        order = db.get(SalesOrder, data.sales_order_id)
        if not order:
            raise HTTPException(404, "Sales order not found")
        if order.status != OrderStatus.ALLOCATED:
            raise HTTPException(409, "Shipment can only be created for an ALLOCATED sales order")
    if data.tracking_number and db.scalar(select(Shipment).where(Shipment.tracking_number == data.tracking_number)):
        raise HTTPException(409, "Tracking number already exists")
    shipment = Shipment(
        shipment_number=shipment_number,
        sales_order_id=data.sales_order_id,
        destination=data.destination,
        carrier=data.carrier,
        tracking_number=data.tracking_number,
        status=data.status,
        dispatch_date=None,
    )
    db.add(shipment)
    db.commit()
    db.refresh(shipment)
    return orm_dict(shipment)


@router.get("/shipments")
def list_shipments(db: Session = Depends(get_db), _: User = Depends(current_user)) -> list[dict[str, Any]]:
    return [orm_dict(item) for item in db.scalars(select(Shipment).order_by(Shipment.created_at.desc()).limit(200))]


@router.post("/exports", status_code=201, dependencies=[Depends(require_roles(UserRole.ADMIN, UserRole.SALES_MANAGER))])
def create_export(data: ExportCreate, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    if db.scalar(select(ExportOrder).where(ExportOrder.export_number == data.export_number)):
        raise HTTPException(409, "Export number already exists")
    warehouse = db.get(Warehouse, data.warehouse_id)
    if not warehouse or not warehouse.active:
        raise HTTPException(404, "Export warehouse not found or inactive")
    batch = db.scalar(select(Batch).where(Batch.id == data.batch_id).with_for_update())
    if not batch or batch.product_id != data.product_id:
        raise HTTPException(404, "Batch/product not found")
    if batch.status != BatchStatus.RELEASED or batch.expiry_date <= date.today():
        raise HTTPException(409, "Export batch is not eligible")
    stock = db.scalar(select(BatchInventory).where(BatchInventory.batch_id == data.batch_id, BatchInventory.product_id == data.product_id, BatchInventory.warehouse_id == data.warehouse_id).with_for_update())
    if not stock:
        raise HTTPException(409, "Export batch stock record not found in selected warehouse")
    if stock.quantity_available < data.quantity or batch.quantity_available < data.quantity:
        raise HTTPException(409, "Insufficient batch stock for export")
    export_payload = data.model_dump(exclude={"warehouse_id"})
    export_payload.update({"destination_country": data.destination_country, "currency": data.currency, "status": "CONFIRMED", "created_by": user.id})
    export = ExportOrder(**export_payload)
    stock.quantity_available -= data.quantity
    batch.quantity_available -= data.quantity
    db.add(export)
    db.add(InventoryMovement(product_id=data.product_id, batch_id=data.batch_id, warehouse_id=data.warehouse_id, quantity=-data.quantity, movement_type=MovementType.SALE, reference_document=data.export_number, user_id=user.id, reason="Export allocation"))
    db.add(AuditLog(user_id=user.id, action="EXPORT_CREATED", entity="ExportOrder", entity_type="ExportOrder", entity_id=str(export.id), reason="Warehouse-authoritative export allocation"))
    db.commit()
    db.refresh(export)
    return orm_dict(export)


@router.get("/reports/inventory")
def inventory_report(db: Session = Depends(get_db), _: User = Depends(current_user)) -> list[dict[str, str]]:
    rows = db.execute(select(BatchInventory.product_id, BatchInventory.warehouse_id, func.sum(BatchInventory.quantity_available).label("quantity_available"), func.sum(BatchInventory.quantity_reserved).label("quantity_reserved")).group_by(BatchInventory.product_id, BatchInventory.warehouse_id)).all()
    return [{"product_id": str(row.product_id), "warehouse_id": str(row.warehouse_id), "quantity_available": str(row.quantity_available or 0), "quantity_reserved": str(row.quantity_reserved or 0), "net_quantity": str(row.quantity_available or 0)} for row in rows]


@router.get("/audit-logs")
def audit_logs(limit: int = Query(default=100, ge=1, le=500), db: Session = Depends(get_db), _: User = Depends(require_roles(UserRole.ADMIN, UserRole.AUDITOR, UserRole.SUPER_ADMIN))) -> list[dict[str, Any]]:
    return [orm_dict(item) for item in db.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit))]
