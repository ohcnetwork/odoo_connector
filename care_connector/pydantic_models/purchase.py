from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class CarePurchaseData(BaseModel):
    facility_uuid: UUID
    item_uuid: UUID
    item_name: str = Field(min_length=1)
    product_id: int = Field(gt=0)
    product_uuid: UUID
    batch: str = ""
    charge_definition_uuid: UUID
    pack_size: int = Field(gt=0)
    base_unit: dict[str, str] = Field(min_length=1)
    received_base_units: Decimal = Field(ge=0, allow_inf_nan=False)


class PurchaseMetadataEntry(BaseModel):
    care_line_uuid: UUID
    care_purchase: CarePurchaseData


class PurchaseMetadataRequest(BaseModel):
    company_id: int | None = Field(default=None, gt=0)
    entries: list[PurchaseMetadataEntry] = Field(min_length=1, max_length=500)
