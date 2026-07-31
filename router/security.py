from fastapi import Security, HTTPException, status
from fastapi.security import APIKeyHeader
from sqlalchemy import select
from model.database import async_session
from model.api_key import ApiKey

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

async def verify_api_key(api_key: str = Security(api_key_header)):
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API Key",
        )
        
    async with async_session() as db:
        result = await db.execute(
            select(ApiKey).where(ApiKey.key_value == api_key, ApiKey.status == "ACTIVE")
        )
        valid_key = result.scalar_one_or_none()
        
    if not valid_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API Key",
        )
    return api_key
