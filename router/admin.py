import secrets
import os
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.responses import FileResponse
from sqlalchemy import select, desc
from pydantic import BaseModel

from model.database import async_session, ADMIN_USERNAME, ADMIN_PASSWORD
from model.order import OrderTracking
from model.merchant import Merchant
from model.api_key import ApiKey
from model.api_log import ApiLog
from model.banned_ip import BannedIp
from model.setting import Setting
import secrets
from typing import Optional
from sqlalchemy import func, delete
from datetime import datetime, timedelta
import psutil
from service.playwright_worker import get_browser_stats

def get_system_metrics() -> dict:
    """Calculates live host and process metrics: CPU, RAM, Storage, Process Memory and Browser stats."""
    try:
        cpu_percent = psutil.cpu_percent(interval=None)
        cpu_count = psutil.cpu_count(logical=True) or 1
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage(os.getcwd())
        proc = psutil.Process()
        proc_mem_mb = round(proc.memory_info().rss / (1024 * 1024), 1)
        
        browser_info = get_browser_stats()
        
        return {
            "cpu": {
                "percent": cpu_percent,
                "cores": cpu_count
            },
            "ram": {
                "total_gb": round(mem.total / (1024 ** 3), 2),
                "used_gb": round(mem.used / (1024 ** 3), 2),
                "free_gb": round(mem.available / (1024 ** 3), 2),
                "percent": mem.percent
            },
            "storage": {
                "total_gb": round(disk.total / (1024 ** 3), 2),
                "used_gb": round(disk.used / (1024 ** 3), 2),
                "free_gb": round(disk.free / (1024 ** 3), 2),
                "percent": disk.percent
            },
            "process": {
                "memory_mb": proc_mem_mb
            },
            "browser": browser_info
        }
    except Exception as e:
        return {
            "error": str(e),
            "cpu": {"percent": 0, "cores": 1},
            "ram": {"total_gb": 0, "used_gb": 0, "free_gb": 0, "percent": 0},
            "storage": {"total_gb": 0, "used_gb": 0, "free_gb": 0, "percent": 0},
            "process": {"memory_mb": 0},
            "browser": {"is_running": False, "active_contexts": 0}
        }

class ApiKeyCreateRequest(BaseModel):
    name: str
    description: str = ""

class ApiKeyUpdateRequest(BaseModel):
    name: str
    description: str = ""
    status: str

class MerchantCreateRequest(BaseModel):
    code_merchant: str
    name: str
    description: str = ""
    merchant_logo_url: str = ""
    payment_link_khr: str
    payment_link_usd: str
    status: str = "ACTIVE"

class MerchantUpdateRequest(BaseModel):
    name: str
    description: str = ""
    merchant_logo_url: str = ""
    payment_link_khr: str
    payment_link_usd: str
    status: str

class BanIpRequest(BaseModel):
    ip_address: str
    reason: str = ""

class SettingsUpdateRequest(BaseModel):
    cors_origins: str

router = APIRouter()
security = HTTPBasic()

def get_current_admin(credentials: HTTPBasicCredentials = Depends(security)):
    correct_username = secrets.compare_digest(credentials.username, ADMIN_USERNAME)
    correct_password = secrets.compare_digest(credentials.password, ADMIN_PASSWORD)
    
    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username

@router.api_route("/", methods=["GET", "HEAD"], response_class=FileResponse)
async def admin_dashboard_ui():
    return FileResponse("static/index.html")

@router.get("/api/v1/admin/data")
async def get_admin_data(admin: str = Depends(get_current_admin)):
    async with async_session() as db:
        # Fetch Orders
        result = await db.execute(select(OrderTracking).order_by(desc(OrderTracking.id)).limit(50))
        orders = result.scalars().all()
        
        # Fetch Merchants
        merch_res = await db.execute(select(Merchant).order_by(Merchant.created_at.desc()))
        merchants = merch_res.scalars().all()
        
        # Fetch API Keys
        key_res = await db.execute(select(ApiKey).order_by(ApiKey.created_at.desc()))
        api_keys = key_res.scalars().all()
        
        # Fetch API Logs
        log_res = await db.execute(select(ApiLog).order_by(ApiLog.created_at.desc()).limit(100))
        api_logs = log_res.scalars().all()
    
    order_list = []
    for o in orders:
        order_list.append({
            "id": o.id,
            "code_merchant": o.code_merchant,
            "amount": o.amount,
            "currency": o.currency,
            "merchant_name": o.merchant_name,
            "status": o.status,
            "tran_id": o.tran_id,
            "updated_at": o.updated_at.isoformat() if o.updated_at else None
        })
        
    merchant_list = []
    for m in merchants:
        merchant_list.append({
            "code_merchant": m.code_merchant,
            "name": m.name,
            "description": m.description,
            "merchant_logo_url": m.merchant_logo_url,
            "payment_link_khr": m.payment_link_khr,
            "payment_link_usd": m.payment_link_usd,
            "status": m.status,
            "created_at": m.created_at.isoformat() if m.created_at else None
        })
        
    api_key_list = []
    for k in api_keys:
        api_key_list.append({
            "id": k.id,
            "key_value": k.key_value,
            "name": k.name,
            "description": k.description,
            "status": k.status,
            "created_at": k.created_at.isoformat() if k.created_at else None
        })
        
    api_log_list = []
    for l in api_logs:
        api_log_list.append({
            "id": l.id,
            "endpoint": l.endpoint,
            "method": l.method,
            "ip_address": l.ip_address,
            "country": l.country,
            "created_at": l.created_at.isoformat() if l.created_at else None
        })
        
    return {
        "merchants": merchant_list,
        "orders": order_list,
        "api_keys": api_key_list,
        "api_logs": api_log_list
    }

@router.get("/api/v1/admin/dashboard")
async def get_admin_dashboard(admin: str = Depends(get_current_admin)):
    async with async_session() as db:
        # Total counts
        total_orders_res = await db.execute(select(func.count(OrderTracking.id)))
        total_orders = total_orders_res.scalar() or 0
        
        success_orders_res = await db.execute(select(func.count(OrderTracking.id)).where(OrderTracking.status == 'SUCCESS'))
        success_orders = success_orders_res.scalar() or 0
        
        merchants_res = await db.execute(select(func.count(Merchant.code_merchant)).where(Merchant.status == 'ACTIVE'))
        active_merchants = merchants_res.scalar() or 0
        
        api_keys_res = await db.execute(select(func.count(ApiKey.id)).where(ApiKey.status == 'ACTIVE'))
        active_api_keys = api_keys_res.scalar() or 0
        
        # Revenue
        # Amount is stored as string, we can fetch all SUCCESS amounts and sum in python
        # or use sqlite casting. Let's fetch and sum to be safe.
        success_amount_res = await db.execute(select(OrderTracking.amount, OrderTracking.currency).where(OrderTracking.status == 'SUCCESS'))
        success_amounts = success_amount_res.all()
        
        total_revenue_usd = sum([float(r[0]) for r in success_amounts if r[1] == 'USD' and r[0]])
        total_revenue_khr = sum([float(r[0]) for r in success_amounts if r[1] == 'KHR' and r[0]])
        
        # 7 Day Trend
        seven_days_ago = datetime.now() - timedelta(days=7)
        recent_orders_res = await db.execute(select(OrderTracking.updated_at, OrderTracking.status, OrderTracking.amount, OrderTracking.currency).where(OrderTracking.updated_at >= seven_days_ago))
        recent_orders = recent_orders_res.all()
        
        # Aggregate by date
        trend_data = {}
        for i in range(7):
            d = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
            trend_data[d] = {"date": d, "total": 0, "success": 0, "amount_usd": 0.0, "amount_khr": 0.0}
            
        for r in recent_orders:
            if not r[0]: continue
            d = r[0].strftime('%Y-%m-%d')
            if d in trend_data:
                trend_data[d]["total"] += 1
                if r[1] == 'SUCCESS':
                    trend_data[d]["success"] += 1
                    amount = float(r[2]) if r[2] else 0.0
                    currency = r[3]
                    if currency == 'USD':
                        trend_data[d]["amount_usd"] += amount
                    elif currency == 'KHR':
                        trend_data[d]["amount_khr"] += amount
                    
        trend_list = [trend_data[d] for d in sorted(trend_data.keys())]

        # Recent tasks (Live status)
        recent_tasks_res = await db.execute(select(OrderTracking).order_by(desc(OrderTracking.id)).limit(20))
        recent_tasks_raw = recent_tasks_res.scalars().all()
        recent_tasks = []
        for t in recent_tasks_raw:
            recent_tasks.append({
                "id": t.id,
                "code_merchant": t.code_merchant,
                "amount": t.amount,
                "currency": t.currency,
                "merchant_name": t.merchant_name,
                "status": t.status,
                "tran_id": t.tran_id,
                "receipt_link": t.receipt_link,
                "updated_at": t.updated_at.isoformat() if t.updated_at else None
            })

        sys_metrics = get_system_metrics()

        return {
            "total_orders": total_orders,
            "success_orders": success_orders,
            "active_merchants": active_merchants,
            "active_api_keys": active_api_keys,
            "total_revenue_usd": total_revenue_usd,
            "total_revenue_khr": total_revenue_khr,
            "trend": trend_list,
            "system_metrics": sys_metrics,
            "recent_tasks": recent_tasks
        }

@router.get("/api/v1/admin/live-status")
async def get_admin_live_status(admin: str = Depends(get_current_admin)):
    async with async_session() as db:
        recent_tasks_res = await db.execute(select(OrderTracking).order_by(desc(OrderTracking.id)).limit(20))
        recent_tasks_raw = recent_tasks_res.scalars().all()
        recent_tasks = []
        for t in recent_tasks_raw:
            recent_tasks.append({
                "id": t.id,
                "code_merchant": t.code_merchant,
                "amount": t.amount,
                "currency": t.currency,
                "merchant_name": t.merchant_name,
                "status": t.status,
                "tran_id": t.tran_id,
                "receipt_link": t.receipt_link,
                "updated_at": t.updated_at.isoformat() if t.updated_at else None
            })
            
    sys_metrics = get_system_metrics()
    return {
        "system_metrics": sys_metrics,
        "recent_tasks": recent_tasks,
        "active_tasks_count": sys_metrics.get("browser", {}).get("active_contexts", 0)
    }

@router.get("/api/v1/admin/ledger")
async def get_admin_ledger(
    admin: str = Depends(get_current_admin),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    status: Optional[str] = None,
    merchant_name: Optional[str] = None,
    search: Optional[str] = None
):
    async with async_session() as db:
        query = select(OrderTracking)
        
        if start_date:
            try:
                start_dt = datetime.fromisoformat(start_date.replace("Z", "+00:00")).replace(tzinfo=None)
                query = query.where(OrderTracking.updated_at >= start_dt)
            except ValueError:
                pass
                
        if end_date:
            try:
                end_dt = datetime.fromisoformat(end_date.replace("Z", "+00:00")).replace(tzinfo=None) + timedelta(days=1, microseconds=-1)
                query = query.where(OrderTracking.updated_at <= end_dt)
            except ValueError:
                pass
                
        if status and status != "ALL":
            query = query.where(OrderTracking.status == status)
            
        if merchant_name and merchant_name != "ALL":
            query = query.where(OrderTracking.merchant_name == merchant_name)
            
        if search:
            search_term = f"%{search}%"
            query = query.where(
                (OrderTracking.code_merchant.ilike(search_term)) |
                (OrderTracking.merchant_name.ilike(search_term)) |
                (OrderTracking.tran_id.ilike(search_term))
            )
            
        orders_res = await db.execute(query.order_by(desc(OrderTracking.id)).limit(1000))
        orders = orders_res.scalars().all()
        
        order_list = []
        for o in orders:
            order_list.append({
                "id": o.id,
                "code_merchant": o.code_merchant,
                "amount": o.amount,
                "currency": o.currency,
                "merchant_name": o.merchant_name,
                "status": o.status,
                "tran_id": o.tran_id,
                "updated_at": o.updated_at.isoformat() if o.updated_at else None
            })
            
        all_merchants_res = await db.execute(select(func.distinct(OrderTracking.merchant_name)))
        available_merchants = [m[0] for m in all_merchants_res.all() if m[0]]
            
        return {
            "orders": order_list,
            "available_merchants": available_merchants
        }

@router.get("/api/v1/admin/analytics")
async def get_admin_analytics(
    admin: str = Depends(get_current_admin),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    method: Optional[str] = None,
    country: Optional[str] = None,
    search: Optional[str] = None
):
    async with async_session() as db:
        # Base query for logs
        query = select(ApiLog)
        
        if start_date:
            try:
                start_dt = datetime.fromisoformat(start_date.replace("Z", "+00:00")).replace(tzinfo=None)
                query = query.where(ApiLog.created_at >= start_dt)
            except ValueError:
                pass
        
        if end_date:
            try:
                end_dt = datetime.fromisoformat(end_date.replace("Z", "+00:00")).replace(tzinfo=None) + timedelta(days=1, microseconds=-1)
                query = query.where(ApiLog.created_at <= end_dt)
            except ValueError:
                pass
                
        if method and method != "ALL":
            query = query.where(ApiLog.method == method)
            
        if country and country != "ALL":
            query = query.where(ApiLog.country == country)
            
        if search:
            search_term = f"%{search}%"
            query = query.where(
                (ApiLog.endpoint.like(search_term)) | 
                (ApiLog.token_name.like(search_term)) |
                (ApiLog.ip_address.like(search_term))
            )
            
        # 1. Total Requests
        total_res = await db.execute(select(func.count(ApiLog.id)).select_from(query.subquery()))
        total_requests = total_res.scalar() or 0
        
        # 2. Total IPs
        ip_res = await db.execute(select(func.count(func.distinct(ApiLog.ip_address))).select_from(query.subquery()))
        total_ips = ip_res.scalar() or 0
        
        # 3. Total Countries
        country_res = await db.execute(select(func.count(func.distinct(ApiLog.country))).select_from(query.subquery()))
        total_countries = country_res.scalar() or 0
        
        # 4. Token usage
        token_query = select(ApiLog.token_name, func.count(ApiLog.id)).select_from(query.subquery()).group_by(ApiLog.token_name).order_by(func.count(ApiLog.id).desc())
        token_res = await db.execute(token_query)
        token_usage = [{"token_name": row[0] or "Anonymous", "count": row[1]} for row in token_res.all()]
        
        # 4.5 Country usage
        country_query = select(ApiLog.country, func.count(ApiLog.id)).select_from(query.subquery()).group_by(ApiLog.country).order_by(func.count(ApiLog.id).desc())
        country_res = await db.execute(country_query)
        country_usage = [{"country": row[0] or "Unknown", "count": row[1]} for row in country_res.all()]
        
        # 5. Fetch logs list (limit 500 for UI)
        logs_query = query.order_by(ApiLog.created_at.desc()).limit(500)
        logs_res = await db.execute(logs_query)
        logs = logs_res.scalars().all()
        
        api_log_list = []
        for l in logs:
            api_log_list.append({
                "id": l.id,
                "endpoint": l.endpoint,
                "method": l.method,
                "ip_address": l.ip_address,
                "country": l.country,
                "token_name": l.token_name,
                "created_at": l.created_at.isoformat() if l.created_at else None
            })
            
        # Fetch unique countries for filter dropdown
        all_countries_res = await db.execute(select(func.distinct(ApiLog.country)))
        available_countries = [c[0] for c in all_countries_res.all() if c[0]]
            
        return {
            "summary": {
                "total_requests": total_requests,
                "total_ips": total_ips,
                "total_countries": total_countries,
                "token_usage": token_usage,
                "country_usage": country_usage
            },
            "available_countries": available_countries,
            "logs": api_log_list
        }

@router.delete("/api/v1/admin/analytics/clear")
async def clear_admin_analytics(admin: str = Depends(get_current_admin)):
    async with async_session() as db:
        await db.execute(delete(ApiLog))
        await db.commit()
    return {"message": "All API logs cleared."}

@router.post("/api/v1/admin/banned_ips")
async def ban_ip(payload: BanIpRequest, admin: str = Depends(get_current_admin)):
    async with async_session() as db:
        existing = await db.execute(select(BannedIp).where(BannedIp.ip_address == payload.ip_address))
        if existing.scalars().first():
            raise HTTPException(status_code=400, detail="IP is already banned")
            
        banned = BannedIp(ip_address=payload.ip_address, reason=payload.reason)
        db.add(banned)
        await db.commit()
    return {"message": f"IP {payload.ip_address} has been banned."}

@router.get("/api/v1/admin/settings")
async def get_settings(admin: str = Depends(get_current_admin)):
    async with async_session() as db:
        res = await db.execute(select(Setting).where(Setting.key == 'cors_origins'))
        setting = res.scalar_one_or_none()
        
        db_size = 0
        if os.path.exists("aba_automation.db"):
            db_size = os.path.getsize("aba_automation.db")
            
        return {
            "cors_origins": setting.value if setting else "*",
            "db_size_bytes": db_size
        }

@router.put("/api/v1/admin/settings")
async def update_settings(payload: SettingsUpdateRequest, admin: str = Depends(get_current_admin)):
    async with async_session() as db:
        res = await db.execute(select(Setting).where(Setting.key == 'cors_origins'))
        setting = res.scalar_one_or_none()
        if setting:
            setting.value = payload.cors_origins
        else:
            setting = Setting(key='cors_origins', value=payload.cors_origins)
            db.add(setting)
        await db.commit()
    return {"message": "Settings updated"}

@router.post("/api/v1/admin/merchants")
async def create_merchant(payload: MerchantCreateRequest, admin: str = Depends(get_current_admin)):
    async with async_session() as db:
        new_merchant = Merchant(
            code_merchant=payload.code_merchant,
            name=payload.name,
            description=payload.description,
            merchant_logo_url=payload.merchant_logo_url,
            payment_link_khr=payload.payment_link_khr,
            payment_link_usd=payload.payment_link_usd,
            status=payload.status
        )
        db.add(new_merchant)
        await db.commit()
    return {"message": "Merchant created successfully"}

@router.put("/api/v1/admin/merchants/{code_merchant}")
async def update_merchant(code_merchant: str, payload: MerchantUpdateRequest, admin: str = Depends(get_current_admin)):
    async with async_session() as db:
        result = await db.execute(select(Merchant).where(Merchant.code_merchant == code_merchant))
        merchant = result.scalar_one_or_none()
        if not merchant:
            raise HTTPException(status_code=404, detail="Merchant not found")
        
        merchant.name = payload.name
        merchant.description = payload.description
        merchant.merchant_logo_url = payload.merchant_logo_url
        merchant.payment_link_khr = payload.payment_link_khr
        merchant.payment_link_usd = payload.payment_link_usd
        merchant.status = payload.status
        await db.commit()
    return {"message": "Merchant updated successfully"}

@router.post("/api/v1/admin/apikeys")
async def create_api_key(payload: ApiKeyCreateRequest, admin: str = Depends(get_current_admin)):
    async with async_session() as db:
        new_key = ApiKey(
            key_value=f"sk_{secrets.token_urlsafe(32)}",
            name=payload.name,
            description=payload.description
        )
        db.add(new_key)
        await db.commit()
    return {"message": "API Key created successfully"}

@router.put("/api/v1/admin/apikeys/{key_id}")
async def update_api_key(key_id: str, payload: ApiKeyUpdateRequest, admin: str = Depends(get_current_admin)):
    async with async_session() as db:
        result = await db.execute(select(ApiKey).where(ApiKey.id == key_id))
        key = result.scalar_one_or_none()
        if not key:
            raise HTTPException(status_code=404, detail="API Key not found")
        
        key.name = payload.name
        key.description = payload.description
        key.status = payload.status
        await db.commit()
    return {"message": "API Key updated"}

@router.delete("/api/v1/admin/apikeys/{key_id}")
async def delete_api_key(key_id: str, admin: str = Depends(get_current_admin)):
    async with async_session() as db:
        result = await db.execute(select(ApiKey).where(ApiKey.id == key_id))
        key = result.scalar_one_or_none()
        if not key:
            raise HTTPException(status_code=404, detail="API Key not found")
        
        await db.delete(key)
        await db.commit()
    return {"message": "API Key deleted"}
