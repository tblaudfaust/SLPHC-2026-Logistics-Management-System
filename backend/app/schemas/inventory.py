import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field, model_validator


class GoodsReceiptItemCreate(BaseModel):
    category_id: uuid.UUID | None = None
    new_category_name: str | None = Field(
        default=None, description="Set instead of category_id to create a new quantity-tracked category inline"
    )
    quantity: int = Field(gt=0)

    @model_validator(mode="after")
    def _require_one_of_category(self) -> "GoodsReceiptItemCreate":
        if not self.category_id and not (self.new_category_name and self.new_category_name.strip()):
            raise ValueError("Provide either category_id or new_category_name.")
        if self.category_id and self.new_category_name:
            raise ValueError("Provide only one of category_id or new_category_name, not both.")
        return self


class GoodsReceiptCreate(BaseModel):
    warehouse_id: uuid.UUID
    supplier_id: uuid.UUID | None = None
    procurement_id: uuid.UUID | None = None
    # received_by_name is deliberately not a client-supplied field: it is
    # always the authenticated caller (app.models.user.User.full_name), so
    # the accountability record can't be typed to name someone other than
    # whoever actually submitted the receipt.
    delivered_by_name: str | None = Field(default=None, description="Name of the person who delivered the goods")
    receipt_date: date | None = None
    """Defaults to today if omitted."""
    items: list[GoodsReceiptItemCreate] = Field(min_length=1)
    remarks: str | None = None


class StockTransferCreate(BaseModel):
    category_id: uuid.UUID
    from_warehouse_id: uuid.UUID
    to_warehouse_id: uuid.UUID
    quantity: int = Field(gt=0)
    expected_delivery_date: date = Field(description="When the receiving warehouse should expect this to arrive")
    # released_by_name/received_by_name are deliberately not client-supplied
    # fields (same reasoning as GoodsReceiptCreate above): always the
    # authenticated caller, so the accountability record can't be typed to
    # name someone other than whoever actually submitted the action.
    reason: str | None = None


class StockAdjustmentCreate(BaseModel):
    warehouse_id: uuid.UUID
    category_id: uuid.UUID
    quantity_delta: int = Field(description="Signed correction — positive adds stock, negative removes it")
    reason: str = Field(min_length=1, description="Mandatory (brief §8.1: 'Approved correction with reason')")


class CategorySummary(BaseModel):
    id: uuid.UUID
    name: str
    code_prefix: str

    model_config = {"from_attributes": True}


class WarehouseLocationSummary(BaseModel):
    id: uuid.UUID
    name: str

    model_config = {"from_attributes": True}


class InventoryTransactionRead(BaseModel):
    id: uuid.UUID
    warehouse: WarehouseLocationSummary
    category: CategorySummary
    transaction_type: str
    quantity: int
    related_warehouse: WarehouseLocationSummary | None
    reference_type: str | None
    reference_id: str | None
    reason: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class SupplierSummary(BaseModel):
    id: uuid.UUID
    name: str
    supplier_type: str

    model_config = {"from_attributes": True}


class GoodsReceiptRead(BaseModel):
    id: uuid.UUID
    warehouse: WarehouseLocationSummary
    supplier: SupplierSummary | None
    procurement_id: uuid.UUID | None
    received_by_name: str
    delivered_by_name: str | None
    receipt_date: date
    remarks: str | None
    items: list[InventoryTransactionRead]
    created_at: datetime

    model_config = {"from_attributes": True}


class StockTransferRead(BaseModel):
    id: uuid.UUID
    category: CategorySummary
    from_warehouse: WarehouseLocationSummary
    to_warehouse: WarehouseLocationSummary
    quantity: int
    status: str
    expected_delivery_date: date
    actual_delivery_date: date | None
    released_by_name: str
    received_by_name: str | None
    reason: str | None
    is_overdue: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class StockBalance(BaseModel):
    warehouse_id: uuid.UUID
    warehouse_name: str
    category_id: uuid.UUID
    category_name: str
    quantity_on_hand: int


class StockCountItemCreate(BaseModel):
    category_id: uuid.UUID
    physical_quantity: int = Field(ge=0)
    variance_reason: str | None = None


class StockCountCreate(BaseModel):
    warehouse_id: uuid.UUID
    count_date: date
    items: list[StockCountItemCreate] = Field(min_length=1)
    notes: str | None = None


class StockCountItemRead(BaseModel):
    id: uuid.UUID
    category: CategorySummary
    expected_quantity: int
    physical_quantity: int
    variance: int
    variance_reason: str | None

    model_config = {"from_attributes": True}


class StockCountRead(BaseModel):
    id: uuid.UUID
    warehouse_id: uuid.UUID
    status: str
    count_date: date
    notes: str | None
    items: list[StockCountItemRead]

    model_config = {"from_attributes": True}
