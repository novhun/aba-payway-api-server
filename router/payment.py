from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse
from sqlalchemy import select

from schema.payment import CheckoutRequest
from model.database import async_session
from model.order import OrderTracking
from model.merchant import Merchant
from service.playwright_worker import run_payment_worker
from router.security import verify_api_key
from fastapi import Depends

router = APIRouter(prefix="/api/v1/payment")

@router.post("/create", dependencies=[Depends(verify_api_key)])
async def create_payment_invoice(payload: CheckoutRequest, background_tasks: BackgroundTasks):
    currency_clean = payload.currency.upper()
    if currency_clean not in ["KHR", "USD"]:
        raise HTTPException(status_code=400, detail="Use 'KHR' or 'USD'")

    async with async_session() as db:
        merchant_result = await db.execute(select(Merchant).where(Merchant.code_merchant == payload.code_merchant))
        merchant = merchant_result.scalar_one_or_none()
        
        if not merchant or merchant.status != "ACTIVE":
            raise HTTPException(status_code=400, detail="Invalid or inactive merchant code")

        new_order = OrderTracking(
            amount=payload.amount, 
            currency=currency_clean, 
            code_merchant=payload.code_merchant, 
            status='PENDING'
        )
        db.add(new_order)
        await db.commit()
        await db.refresh(new_order)
        inserted_id = new_order.id
    print(f"API REQUEST: Created ledger context instance entry row inside database model. ID: {inserted_id}")

    target_link = merchant.payment_link_usd if currency_clean == "USD" else merchant.payment_link_khr
    background_tasks.add_task(run_payment_worker, inserted_id, payload.amount, currency_clean, target_link)
    return {"invoice_id": inserted_id, "payment_status": "PROCESSING"}

@router.get("/verify/{invoice_id}", dependencies=[Depends(verify_api_key)])
async def fetch_invoice_status_api(invoice_id: int):
    async with async_session() as db:
        result = await db.execute(select(OrderTracking).where(OrderTracking.id == invoice_id))
        order = result.scalar_one_or_none()
        if order:
            return {
                "invoice_id": order.id,
                "amount": order.amount,
                "currency": order.currency,
                "status": order.status,
                "khqr": order.khqr_data,
                "receipt": order.receipt_link
            }
    raise HTTPException(status_code=404, detail="Order reference identifier not located.")

@router.get("/qr-code/verify/{invoice_id}", response_class=HTMLResponse)
async def fetch_invoice_status_qr(invoice_id: int):
    async with async_session() as db:
        result = await db.execute(select(OrderTracking).where(OrderTracking.id == invoice_id))
        order = result.scalar_one_or_none()
            
    if not order:
        raise HTTPException(status_code=404, detail="Order reference not located.")
        
    amount = order.amount
    currency = order.currency
    status = order.status
    qr_base64 = order.qr_base64
    merchant_name = order.merchant_name

    if not qr_base64:
        return """
        <html>
        <head>
            <meta http-equiv="refresh" content="3">
        </head>
        <body style="font-family: sans-serif; text-align: center; padding: 40px; color: #666;">
            <h3>Generating securing KHQR Code Matrix...</h3>
            <p>Please wait a moment while we build the runtime image components.</p>
        </body>
        </html>
        """

    if status == "SUCCESS":
        return f"""
        <div style="font-family: sans-serif; text-align: center; padding: 40px; max-width: 350px; margin: auto; background: #fff; border-radius: 24px; border: 1px solid #e0e0e0;">
            <div style="font-size: 56px; color: #3caf47;">✓</div>
            <h2 style="color: #333; margin-top: 10px;">Payment Verified!</h2>
            <p style="color: #666;">Thank you. Your payment of {int(amount):,} {currency} has been credited to {merchant_name}.</p>
        </div>
        """

    if status == "EXPIRED" or status == "FAILED":
        return f"""
        <div style="font-family: sans-serif; text-align: center; padding: 40px; max-width: 350px; margin: auto; background: #fff; border-radius: 24px; border: 1px solid #e0e0e0;">
            <div style="font-size: 56px; color: #ed1116;">✗</div>
            <h2 style="color: #333; margin-top: 10px;">Payment {status.capitalize()}</h2>
            <p style="color: #666;">This QR code is no longer valid. Please generate a new one.</p>
        </div>
        """

    return f"""
    <payment-card style="display: block; width: 350px; background: #ffffff; border-radius: 24px; box-shadow: 0 4px 20px rgba(0,0,0,0.04); overflow: hidden; border: 1px solid #f0f0f0; box-sizing: border-box; font-family: sans-serif; margin: auto;">
        <card-header style="display: flex; justify-content: center; align-items: center; height: 90px; background: #ed1116; position: relative;">
            <brand-logo style="display: flex; justify-content: center; align-items: center; color: #ffffff; width: 100%;">
                <svg width="90" height="21" viewBox="0 0 60 14" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M39.006 5.19439V9.59764H34.5318C34.0729 9.59764 33.7288 9.2307 33.7288 8.80731V5.22264C33.7288 4.77103 34.1016 4.43231 34.5318 4.43231H38.1743C38.6619 4.40408 39.006 4.74278 39.006 5.19439Z" fill="white"/>
                <path d="M59.9717 6.97176H57.7345C57.7345 4.34676 55.5548 2.20159 52.8875 2.20159C50.7651 2.20159 48.9008 3.55645 48.2699 5.53225C48.1265 6.01209 48.0404 6.49192 48.0404 6.97176V13.9718H47.9831C46.7785 13.9718 45.8033 13.0121 45.8033 11.8266V6.97176H45.832C45.832 5.05241 46.6351 3.21773 48.0691 1.89112C49.3884 0.677406 51.1093 0 52.9162 0C56.8168 0 59.9717 3.13305 59.9717 6.97176Z" fill="white"/>
                <path d="M59.9999 13.9718L56.845 14L56.0706 13.2379L54.3497 11.5444L51.9692 9.20166H55.1241L59.9999 13.9718Z" fill="white"/>
                <path d="M39.7517 11.7702H33.0117C32.1799 11.7702 31.5203 11.121 31.5203 10.3024V3.66936C31.5203 2.85081 32.1799 2.20159 33.0117 2.20159H39.7517C40.5834 2.20159 41.2431 2.85081 41.2431 3.66936V10.3024L43.4802 12.504V2.14515C43.4802 0.959671 42.505 0 41.3005 0H31.4629C30.2583 0 29.2832 0.959671 29.2832 2.14515V11.8266C29.2832 13.0121 30.2583 13.9718 31.4629 13.9718H41.9888L39.7517 11.7702Z" fill="white"/>
                <path d="M12.3614 14H9.20656L2.60996 7.47984V14H0V0H2.60996V6.2379L8.94843 0H12.046L5.16255 6.71772L12.3614 14Z" fill="white"/>
                <path d="M24.1492 0H26.7018V14H24.1492V7.93145H16.8643V14H14.3117V0H16.8643V5.84273H24.1492V0Z" fill="white"/>
                </svg>
            </brand-logo>
            <div style="position: absolute; right: 0; bottom: -42px; width: 0; height: 0; border-top: 50px solid transparent; border-right: 50px solid #ed1116; border-bottom: 42px solid transparent;"></div>
        </card-header>

        <card-body style="display: block; padding: 30px 24px 24px 24px; box-sizing: border-box;">
            <account-holder style="display: block; font-size: 16px; color: #333333; font-weight: 600; letter-spacing: 0.5px; text-transform: uppercase;">{merchant_name}</account-holder>
            
            <display-amount style="display: block; font-size: 42px; font-weight: bold; color: #111111; margin-top: 8px;">
                {int(amount):,} <span style="font-size: 18px; font-weight: 500; color: #666; margin-left: 2px;">{currency}</span>
            </display-amount>

            <dashed-divider style="display: block; border-top: 2px dashed #e0e0e0; margin: 22px 0;"></dashed-divider>

            <qr-wrapper style="display: flex; justify-content: center; align-items: center; padding: 5px;">
                <img src="{qr_base64}" alt="Payment QR Code" style="width: 250px; height: 250px; object-fit: contain;">
            </qr-wrapper>
            
            <p style="text-align: center; color: #878787; font-size: 12px; margin-top: 15px; margin-bottom: 0; line-height: 16px;">
                អាចទូទាត់ប្រាក់តាមធនាគារដែលគាំទ្រ QRCODE KHQR 
            </p>
        </card-body>
    </payment-card>
    """
