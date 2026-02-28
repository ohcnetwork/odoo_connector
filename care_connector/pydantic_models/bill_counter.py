from pydantic import BaseModel

class BillCounterData(BaseModel):
    x_care_id: str
    cashier_id: str
    counter_name: str