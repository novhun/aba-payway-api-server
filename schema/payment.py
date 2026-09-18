from typing import Optional
from pydantic import BaseModel

class CheckoutRequest(BaseModel):
    code_merchant: str
    amount: str
    currency: str
    callback_url: Optional[str] = None

class StatusResponse(BaseModel):
    status: str
    version: str
