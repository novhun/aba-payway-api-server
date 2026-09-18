import asyncio
import httpx
from datetime import datetime
from sqlalchemy import update
from model.database import async_session
from model.order import OrderTracking

async def send_payment_webhook(order_id: int, callback_url: str, event: str, payload_data: dict, max_retries: int = 3):
    """
    Dispatches an asynchronous HTTP POST webhook to the merchant's callback URL.
    Includes retry backoff on failures and updates OrderTracking.webhook_status.
    """
    if not callback_url or not callback_url.strip():
        return

    callback_url = callback_url.strip()
    
    webhook_payload = {
        "event": event,
        "invoice_id": order_id,
        "tran_id": payload_data.get("tran_id") or "",
        "amount": str(payload_data.get("amount") or "0"),
        "currency": payload_data.get("currency") or "USD",
        "status": payload_data.get("status") or "SUCCESS",
        "merchant_name": payload_data.get("merchant_name") or "",
        "code_merchant": payload_data.get("code_merchant") or "",
        "receipt_link": payload_data.get("receipt_link") or "",
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }

    headers = {
        "Content-Type": "application/json",
        "User-Agent": "DigitalKH-PayWay-Webhook/1.0",
        "X-PayWay-Event": event,
        "X-PayWay-Invoice-Id": str(order_id)
    }

    print(f"\nLOG: [Webhook-{order_id}] Dispatching '{event}' to {callback_url}...")
    success = False

    for attempt in range(1, max_retries + 1):
        try:
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                res = await client.post(callback_url, json=webhook_payload, headers=headers)
                if 200 <= res.status_code < 300:
                    print(f"SUCCESS: [Webhook-{order_id}] Delivered successfully to {callback_url} (HTTP {res.status_code})")
                    success = True
                    break
                else:
                    print(f"WARN: [Webhook-{order_id}] Attempt {attempt}/{max_retries} failed with HTTP {res.status_code}")
        except Exception as e:
            print(f"WARN: [Webhook-{order_id}] Attempt {attempt}/{max_retries} network error: {str(e)}")

        if attempt < max_retries:
            await asyncio.sleep(attempt * 2)

    status_str = "DELIVERED" if success else "FAILED"
    try:
        async with async_session() as db:
            await db.execute(
                update(OrderTracking)
                .where(OrderTracking.id == order_id)
                .values(webhook_status=status_str)
            )
            await db.commit()
    except Exception as e:
        print(f"ERROR: [Webhook-{order_id}] Failed updating webhook_status in DB: {e}")
