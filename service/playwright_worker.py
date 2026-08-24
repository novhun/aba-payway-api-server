import os
import shutil
import asyncio
import json
from typing import Optional
from playwright.async_api import async_playwright, Playwright, Browser
from sqlalchemy import update

from model.database import async_session
from model.order import OrderTracking
from service.qr_generator import generate_qr_base64, parse_khqr_merchant_name

playwright_instance: Optional[Playwright] = None
browser_instance: Optional[Browser] = None
active_tasks_count: int = 0

def get_browser_stats() -> dict:
    """Returns the current status of the Playwright browser and active contexts."""
    global browser_instance, active_tasks_count
    is_running = False
    try:
        is_running = browser_instance is not None and browser_instance.is_connected()
    except Exception:
        pass
    return {
        "is_running": is_running,
        "active_contexts": active_tasks_count
    }

async def init_browser():
    """Initializes a single global Playwright and Chromium browser instance."""
    global playwright_instance, browser_instance
    if browser_instance is None:
        playwright_instance = await async_playwright().start()

        # Find system-installed Chrome/Chromium if Playwright internal binary isn't available
        executable_path = None
        candidates = [
            shutil.which("google-chrome-stable"),
            shutil.which("google-chrome"),
            shutil.which("chromium"),
            shutil.which("chromium-browser"),
            "/usr/bin/google-chrome-stable",
            "/usr/bin/google-chrome",
            "/usr/bin/chromium",
            "/usr/bin/chromium-browser"
        ]
        for c in candidates:
            if c and os.path.exists(c) and os.access(c, os.X_OK):
                executable_path = c
                break

        launch_args = [
            "--disable-blink-features=AutomationControlled",
            "--disable-gpu",                                         # Disable GPU hardware acceleration
            "--no-sandbox",                                          # Low overhead on Linux
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",                               # Prevent /dev/shm OOM on small VPS
            "--disable-accelerated-2d-canvas",
            "--disable-web-security",
            "--disable-extensions",
            "--disable-default-apps",
            "--disable-sync",
            "--disable-background-networking",
            "--disable-component-update",
            "--disable-domain-reliability",
            "--disable-client-side-phishing-detection",
            "--disable-hang-monitor",
            "--disable-popup-blocking",
            "--disable-prompt-on-repost",
            "--mute-audio",
            "--no-first-run",
            "--no-default-browser-check",
            "--password-store=basic",
            "--use-mock-keychain",
            "--js-flags=--max-old-space-size=128"                    # Restrict V8 JS heap memory
        ]

        launch_kwargs = {
            "headless": True,
            "args": launch_args
        }

        # If system browser is found, use it; otherwise fallback to default playwright chromium
        if executable_path:
            launch_kwargs["executable_path"] = executable_path
            print(f"LOG: [Playwright] Launching optimized system browser: {executable_path}")
            try:
                browser_instance = await playwright_instance.chromium.launch(**launch_kwargs)
            except Exception as e:
                print(f"LOG: [Playwright] System browser launch fallback error: {e}")
                launch_kwargs.pop("executable_path", None)
                browser_instance = await playwright_instance.chromium.launch(**launch_kwargs)
        else:
            browser_instance = await playwright_instance.chromium.launch(**launch_kwargs)

        print("LOG: [Playwright] Global Chromium browser instance launched (Low-CPU Mode).")

async def close_browser():
    """Gracefully shuts down the global Playwright and Chromium browser instance."""
    global playwright_instance, browser_instance
    if browser_instance:
        await browser_instance.close()
        browser_instance = None
    if playwright_instance:
        await playwright_instance.stop()
        playwright_instance = None
    print("LOG: [Playwright] Global Chromium browser instance closed.")

async def run_payment_worker(db_row_id: int, amount: str, currency: str, target_link: str, code_merchant: str = None):
    global browser_instance, active_tasks_count
    if browser_instance is None:
        await init_browser()

    active_tasks_count += 1
    print(f"\nLOG: [Task-{db_row_id}] Spawning isolated context for {amount} {currency.upper()} (Merchant: {code_merchant or 'default'}) (Active Tasks: {active_tasks_count})")
    
    # Create isolated context (equivalent to an incognito tab)
    context = await browser_instance.new_context(
        user_agent="Mozilla/5.0 (Linux; Android 15; Pixel 9) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Mobile Safari/537.36",
        viewport={"width": 393, "height": 851},
        is_mobile=True
    )
    
    # Abort images, media, svg, and web fonts to drastically reduce RAM, CPU & network load
    await context.route(
        "**/*.{png,jpg,jpeg,webp,gif,woff,woff2,ttf,eot,ico,mp4,mp3,svg}",
        lambda route: route.abort()
    )

    page = await context.new_page()

    # Disable all CSS animations on page to prevent CPU spinning on 1-core VPS
    await page.add_init_script("""
        const disableAnimations = () => {
            const style = document.createElement('style');
            style.type = 'text/css';
            style.innerHTML = '* { -webkit-animation: none !important; -moz-animation: none !important; -o-animation: none !important; -ms-animation: none !important; animation: none !important; -webkit-transition: none !important; -moz-transition: none !important; -o-transition: none !important; -ms-transition: none !important; transition: none !important; }';
            document.head && document.head.appendChild(style);
        };
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', disableAnimations);
        } else {
            disableAnimations();
        }
    """)
    state = {"status": "PENDING", "client_id": None, "tran_id": None, "code_merchant": code_merchant}

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

                    # Trigger instant Telegram notification (routes to merchant's custom group or global)
                    from service.telegram_service import send_payment_success_alert
                    asyncio.create_task(send_payment_success_alert({
                        "id": db_row_id,
                        "amount": amount,
                        "currency": currency,
                        "tran_id": state.get("tran_id", "N/A"),
                        "merchant_name": state.get("merchant_name", ""),
                        "code_merchant": code_merchant
                    }))
            except Exception:
                pass

    page.on("response", intercept_network_traffic)

    try:
        print(f"LOG: [Task-{db_row_id}] Dispatching engine target layout...")
        await page.goto(target_link, wait_until="domcontentloaded", timeout=20000)
        
        amount_field = page.locator("#txt_amount")
        await amount_field.wait_for(timeout=10000)
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
        active_tasks_count = max(0, active_tasks_count - 1)
        print(f"LOG: [Task-{db_row_id}] Closing isolated context and cleaning RAM. (Remaining Active Tasks: {active_tasks_count})")
        await context.close()

