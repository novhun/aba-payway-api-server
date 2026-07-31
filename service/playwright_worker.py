import asyncio
import json
from playwright.async_api import async_playwright
from sqlalchemy import update

from model.database import async_session
from model.order import OrderTracking
from service.qr_generator import generate_qr_base64, parse_khqr_merchant_name

async def run_payment_worker(db_row_id: int, amount: str, currency: str, target_link: str):
    print(f"\nLOG: [Task-{db_row_id}] Spawning background instance for {amount} {currency.upper()}")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"]
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Linux; Android 15; Pixel 9) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Mobile Safari/537.36",
            viewport={"width": 393, "height": 851},
            is_mobile=True
        )
        page = await context.new_page()
        state = {"status": "PENDING", "client_id": None, "tran_id": None}

        async def intercept_network_traffic(response):
            url = response.url
            if "check-payment-status" in url:
                try:
                    req_payload = json.loads(response.request.post_data)
                    state["client_id"] = req_payload.get("client_id")
                except Exception:
                    pass
                try:
                    res_json = await response.json()
                    action = res_json.get("data", {}).get("action")
                    print(f"LOG: [Task-{db_row_id}] Status verification polling: '{action}'")
                    
                    if action == "approved":
                        state["status"] = "SUCCESS"
                        receipt_link = res_json.get("data", {}).get("download_receipt")
                        if res_json.get("data", {}).get("message", {}).get("tran_id"):
                            state["tran_id"] = res_json.get("data", {}).get("message", {}).get("tran_id")

                        print(f"SUCCESS: [Task-{db_row_id}] Web ledger transaction approved.")
                        async with async_session() as db:
                            await db.execute(
                                update(OrderTracking)
                                .where(OrderTracking.id == db_row_id)
                                .values(
                                    status='SUCCESS',
                                    client_id=state["client_id"],
                                    receipt_link=receipt_link,
                                    tran_id=state["tran_id"]
                                )
                            )
                            await db.commit()
                except Exception:
                    pass

        page.on("response", intercept_network_traffic)

        try:
            print(f"LOG: [Task-{db_row_id}] Dispatching engine target layout...")
            await page.goto(target_link, wait_until="networkidle")
            
            amount_field = page.locator("#txt_amount")
            await amount_field.wait_for(timeout=7000)
            await amount_field.fill(amount)
            await asyncio.sleep(0.5)
            
            continue_btn = page.locator("button:has-text('Continue'), button:has-text('CONTINUE')")
            await continue_btn.click(force=True)
            print(f"LOG: [Task-{db_row_id}] Input posted. Compiling document target tracking selectors...")

            khqr_element = page.locator("div[value^='000201']")
            await khqr_element.wait_for(timeout=10000)
            khqr_string = await khqr_element.get_attribute("value")
            
            parsed_merchant_name = parse_khqr_merchant_name(khqr_string)
            base64_image_data = generate_qr_base64(khqr_string)

            async with async_session() as db:
                await db.execute(
                    update(OrderTracking)
                    .where(OrderTracking.id == db_row_id)
                    .values(
                        khqr_data=khqr_string,
                        qr_base64=base64_image_data,
                        merchant_name=parsed_merchant_name
                    )
                )
                await db.commit()
            print(f"LOG: [Task-{db_row_id}] Core layout parameters cached successfully.")

            timeout = 120
            poll_interval = 2
            elapsed = 0
            while elapsed < timeout:
                if state["status"] == "SUCCESS":
                    break
                await asyncio.sleep(poll_interval)
                elapsed += poll_interval

            if state["status"] != "SUCCESS":
                print(f"LOG: [Task-{db_row_id}] Timeout reached. Updating status to EXPIRED.")
                async with async_session() as db:
                    await db.execute(
                        update(OrderTracking)
                        .where(OrderTracking.id == db_row_id)
                        .values(status='EXPIRED')
                    )
                    await db.commit()

        except Exception as e:
            print(f"CRITICAL ERROR: [Task-{db_row_id}] Core automation run failure: {str(e)}")
            try:
                async with async_session() as db:
                    await db.execute(
                        update(OrderTracking)
                        .where(OrderTracking.id == db_row_id, OrderTracking.status == 'PENDING')
                        .values(status='FAILED')
                    )
                    await db.commit()
            except Exception:
                pass
        finally:
            print(f"LOG: [Task-{db_row_id}] Closing instance thread clean.")
            await browser.close()
