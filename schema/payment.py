from pydantic import BaseModel

class CheckoutRequest(BaseModel):
    code_merchant: str
    amount: str
    currency: str

class StatusResponse(BaseModel):
    status: str
    version: str
