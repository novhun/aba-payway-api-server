from fastapi import APIRouter
from schema.payment import StatusResponse

router = APIRouter()

@router.get("/status", response_model=StatusResponse)
def get_status():
    """
    Endpoint to check the health and operational status of the API.
    """
    return {"status": "healthy", "version": "1.0.0"}
