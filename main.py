import sys
import os
import sqlite3
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from model.database import engine, Base
from model.order import OrderTracking
from model.merchant import Merchant
from model.setting import Setting
from model.api_key import ApiKey
from model.api_log import ApiLog
from model.banned_ip import BannedIp
from router.system import router as system_router
from router.payment import router as payment_router
from router.admin import router as admin_router
from service.playwright_worker import init_browser, close_browser
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request
import httpx
from model.database import async_session
from sqlalchemy import select
from fastapi.responses import JSONResponse

async def log_request(path: str, method: str, ip: str, token_name: str = None):
    country = "Unknown"
    if ip not in ["127.0.0.1", "::1", "Localhost"]:
        try:
            async with httpx.AsyncClient() as client:
                res = await client.get(f"http://ip-api.com/json/{ip}", timeout=2.0)
                if res.status_code == 200:
                    data = res.json()
                    if data.get("status") == "success":
                        country = data.get("country", "Unknown")
        except Exception:
            pass
    
    async with async_session() as db:
        log_entry = ApiLog(endpoint=path, method=method, ip_address=ip, country=country, token_name=token_name)
        db.add(log_entry)
        await db.commit()

class APILoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        ip = request.client.host if request.client else "Unknown"
        
        # Check if IP is banned
        if ip != "Unknown":
            async with async_session() as db:
                banned_res = await db.execute(select(BannedIp).where(BannedIp.ip_address == ip))
                if banned_res.scalars().first():
                    return JSONResponse(status_code=403, content={"detail": "Your IP has been banned."})
                    
        response = await call_next(request)
        
        path = request.url.path
        if not path.startswith("/assets") and path != "/favicon.ico":
            api_key = request.headers.get("x-api-key")
            token_name = None
            if api_key:
                async with async_session() as db:
                    key_res = await db.execute(select(ApiKey).where(ApiKey.key_value == api_key))
                    key_obj = key_res.scalars().first()
                    if key_obj:
                        token_name = key_obj.name
                        
            asyncio.create_task(log_request(path, request.method, ip, token_name))
            
        return response

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Migrate merchant table to add telegram_chat_id column if not exists
        try:
            from sqlalchemy import text
            await conn.execute(text("ALTER TABLE merchant ADD COLUMN telegram_chat_id VARCHAR DEFAULT ''"))
        except Exception:
            pass
    print("LOG: [Database] Storage tables verified clean.")
    await init_browser()
    from service.telegram_service import start_telegram_poller
    poller_task = asyncio.create_task(start_telegram_poller())
    yield
    if poller_task:
        poller_task.cancel()
    await close_browser()

cors_origins = ["*"]
try:
    if os.path.exists("aba_automation.db"):
        conn = sqlite3.connect("aba_automation.db")
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM setting WHERE key='cors_origins'")
        row = cursor.fetchone()
        if row and row[0]:
            if row[0] != "*":
                cors_origins = [o.strip() for o in row[0].split('\n') if o.strip()]
        conn.close()
except Exception:
    pass

app = FastAPI(title="DigitalKH PayWay Web-Automation Engine", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(APILoggingMiddleware)

app.mount("/assets", StaticFiles(directory="static/assets"), name="assets")

app.include_router(system_router)
app.include_router(payment_router)
app.include_router(admin_router)

if __name__ == "__main__":
    import uvicorn
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    uvicorn.run(app, host="0.0.0.0", port=8001)