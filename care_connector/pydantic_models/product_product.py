from pydantic import BaseModel
from .product_category import CategoryData
from enum import Enum

class TaxData(BaseModel):
    tax_name: str
    tax_percentage : float

class ProductStatus(Enum):
    active = 'active'
    retired = 'retired'
    draft = 'draft'

class ProductData(BaseModel):
    product_name : str
    x_care_id: str
    cost:float | None = None
    mrp:float = 0.0
    category: CategoryData
    taxes : list[TaxData] | None = None
    hsn: str | None = None
    status: ProductStatus | None = None