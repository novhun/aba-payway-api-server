from fastapi import APIRouter
from schema.payment import StatusResponse

router = APIRouter()

@router.api_route("/status", methods=["GET", "HEAD"], response_model=StatusResponse)
def get_status():
    """
    Endpoint to check the health and operational status of the API.
    """
    return {"status": "healthy", "version": "1.0.0"}

@router.api_route("/health", methods=["GET", "HEAD"])
def get_health():
    return {"status": "ok"}
