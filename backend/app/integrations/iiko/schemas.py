from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, Field


class IikoCategory(BaseModel):
    """Category from iiko nomenclature."""
    id: str
    name: str
    parent_id: Optional[str] = Field(None, alias="parentGroup")
    order: int = 0
    is_deleted: bool = Field(False, alias="isDeleted")


class IikoProduct(BaseModel):
    """Product from iiko nomenclature."""
    id: str
    name: str
    description: Optional[str] = None
    parent_group: Optional[str] = Field(None, alias="parentGroup")
    product_category_id: Optional[str] = Field(None, alias="productCategoryId")
    price: Decimal = 0
    is_deleted: bool = Field(False, alias="isDeleted")
    type: str = "Dish"  # Dish, Modifier, etc.
    code: Optional[str] = None
    measurement_unit: str = "pcs"
    image_links: List[str] = Field(default_factory=list, alias="imageLinks")

    class Config:
        populate_by_name = True


class IikoEmployee(BaseModel):
    """Employee from iiko."""
    id: str
    name: str
    code: Optional[str] = None
    role: Optional[str] = None
    is_deleted: bool = Field(False, alias="isDeleted")


class IikoOrderItem(BaseModel):
    """Order item from iiko."""
    product_id: str = Field(alias="productId")
    product_name: str = ""
    amount: Decimal = 1
    sum: Decimal = 0
    price: Decimal = 0


class IikoOrder(BaseModel):
    """Order/receipt from iiko."""
    id: str
    order_id: Optional[str] = Field(None, alias="orderId")
    number: Optional[str] = None
    open_time: datetime = Field(alias="openTime")
    close_time: Optional[datetime] = Field(None, alias="closeTime")
    sum: Decimal = 0
    discount_sum: Decimal = Field(0, alias="discountSum")
    guests_count: int = Field(1, alias="guestsCount")
    table_number: Optional[str] = Field(None, alias="tableNumber")
    waiter_id: Optional[str] = Field(None, alias="waiterId")
    items: List[IikoOrderItem] = Field(default_factory=list)
    payments: List[dict] = Field(default_factory=list)


class IikoNomenclatureResponse(BaseModel):
    """Response from iiko nomenclature endpoint."""
    groups: List[IikoCategory] = Field(default_factory=list)
    products: List[IikoProduct] = Field(default_factory=list)
    revision: int = 0


class IikoOLAPRow(BaseModel):
    """Row from iiko OLAP report."""
    department: Optional[str] = Field(None, alias="Department")
    dish_name: Optional[str] = Field(None, alias="DishName")
    dish_id: Optional[str] = Field(None, alias="DishId")
    dish_sum: Decimal = Field(0, alias="DishSum")
    dish_amount: Decimal = Field(0, alias="DishAmount")
    dish_discount_sum: Decimal = Field(0, alias="DishDiscountSum")
    product_cost: Optional[Decimal] = Field(None, alias="ProductCostBase.ProductCost")
