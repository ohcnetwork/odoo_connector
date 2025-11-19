from pydantic import BaseModel

class CategoryData(BaseModel):
    category_name: str
    x_care_id: str
    parent_x_care_id: str | None = None