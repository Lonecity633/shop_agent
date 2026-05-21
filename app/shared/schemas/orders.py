from pydantic import BaseModel


class OrderToolQuery(BaseModel):
    user_id: int
    order_id: str

