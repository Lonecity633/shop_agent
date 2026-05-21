from pydantic import BaseModel


class RefundStatusQuery(BaseModel):
    user_id: int
    refund_id: int

