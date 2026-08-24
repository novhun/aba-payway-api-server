import os
import httpx
import asyncio
from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy import select

from model.database import async_session
from model.setting import Setting

TELEGRAM_API_BASE = "https://api.telegram.org"

_last_processed_update_id: int = 0
_poller_task: Optional[asyncio.Task] = None

async def get_setting_value(key: str, default: str = "") -> str:
    """Helper to fetch a setting value from database."""
    async with async_session() as db:
        res = await db.execute(select(Setting).where(Setting.key == key))
        setting = res.scalar_one_or_none()
        return setting.value if setting and setting.value else default

async def process_telegram_auto_connect(bot_token: str) -> Dict[str, Any]:
    """
    Scans Telegram updates for merchant connection commands:
    - /start <code_merchant> (from 1-Click invite link ?startgroup=<code_merchant>)
    - /connect <code_merchant>
    - /link <code_merchant>
    Automatically links the chat/group ID to the matching Merchant in the database
    and sends a success confirmation message back to the group.
    """
    global _last_processed_update_id
    if not bot_token:
        return {"ok": False, "error": "Bot token is required"}

    from model.merchant import Merchant

    url = f"{TELEGRAM_API_BASE}/bot{bot_token}/getUpdates"
    params = {"limit": 100}
    if _last_processed_update_id > 0:
        params["offset"] = _last_processed_update_id + 1

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.get(url, params=params)
            data = res.json()
            if not data.get("ok"):
                return {"ok": False, "error": data.get("description", "Failed to fetch updates")}

            raw_updates = data.get("result", [])
            if not raw_updates:
                return {"ok": True, "connected": [], "message": "No new updates"}

            connected_events = []

            bot_info = await get_telegram_bot_info(bot_token)
            bot_id = bot_info.get("id")
            bot_username = bot_info.get("username", "PayWayBot")
            bot_name = bot_info.get("first_name", "ABA PayWay Bot")

            for update in raw_updates:
                up_id = update.get("update_id", 0)
                if up_id > _last_processed_update_id:
                    _last_processed_update_id = up_id

                msg = (
                    update.get("message") or 
                    update.get("edited_message") or 
                    update.get("channel_post")
                )
                my_chat_member = update.get("my_chat_member")

                # Handle bot being added to a group via my_chat_member
                if my_chat_member:
                    new_status = my_chat_member.get("new_chat_member", {}).get("status")
                    chat = my_chat_member.get("chat")
                    if chat and new_status in ["member", "administrator"]:
                        chat_id = str(chat.get("id"))
                        chat_title = chat.get("title") or f"Group {chat_id}"
                        welcome_group_msg = f"""
👋 <b>សួស្តី! / Welcome to ABA PayWay Engine Bot!</b>
━━━━━━━━━━━━━━━━━━
🤖 <b>Status:</b> 🟢 Connected & Verified
👥 <b>Group:</b> {chat_title}
💬 <b>Group Chat ID:</b> <code>{chat_id}</code>
⏱️ <b>Time:</b> {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
━━━━━━━━━━━━━━━━━━
💡 <b>How to link with your Merchant:</b>
1️⃣ Type: <code>/connect &lt;merchant_code&gt;</code> in this group
   <i>(Example: <code>/connect aba_merchant_1</code>)</i>
2️⃣ Or add <code>{chat_id}</code> directly in Admin Dashboard -> Merchants!

🔔 <i>Real-time payment notifications will appear here instantly upon customer payment.</i>
"""
                        await send_raw_telegram_message(bot_token, chat_id, welcome_group_msg.strip())
                    continue

                if not msg:
                    continue

                chat = msg.get("chat")
                if not chat:
                    continue

                chat_id = str(chat.get("id"))
                chat_type = chat.get("type", "unknown")
                chat_title = chat.get("title") or chat.get("first_name") or f"Chat {chat_id}"
                text = (msg.get("text") or msg.get("caption") or "").strip()

                # Check if bot was added in new_chat_members
                new_members = msg.get("new_chat_members", [])
                for member in new_members:
                    if (bot_id and member.get("id") == bot_id) or (member.get("username") == bot_username):
                        welcome_group_msg = f"""
👋 <b>សួស្តី! / Welcome to ABA PayWay Engine Bot!</b>
━━━━━━━━━━━━━━━━━━
🤖 <b>Status:</b> 🟢 Connected & Verified
👥 <b>Group:</b> {chat_title}
💬 <b>Group Chat ID:</b> <code>{chat_id}</code>
⏱️ <b>Time:</b> {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
━━━━━━━━━━━━━━━━━━
💡 <b>How to link with your Merchant:</b>
1️⃣ Type: <code>/connect &lt;merchant_code&gt;</code> in this group
   <i>(Example: <code>/connect aba_merchant_1</code>)</i>
2️⃣ Or add <code>{chat_id}</code> directly in Admin Dashboard -> Merchants!

🔔 <i>Real-time payment notifications will appear here instantly upon customer payment.</i>
"""
                        await send_raw_telegram_message(bot_token, chat_id, welcome_group_msg.strip())
                        break

                target_merchant_code = None

                # Check if message contains /start, /connect, or /link with payload
                # Examples: "/start my_store", "/start@bot my_store", "/connect my_store"
                parts = text.split()
                if parts:
                    cmd = parts[0].lower().split('@')[0]
                    if cmd in ["/start", "/connect", "/link"] and len(parts) >= 2:
                        target_merchant_code = parts[1].strip()
                    elif cmd == "/start" and len(parts) == 1 and chat_type == "private":
                        # Welcome message for private DM
                        dm_welcome = f"""
👋 <b>សួស្តី {chat_title}! / Welcome to ABA PayWay Bot!</b>
━━━━━━━━━━━━━━━━━━
🤖 <b>Bot:</b> {bot_name} (@{bot_username})
👤 <b>Your Telegram User ID:</b> <code>{chat_id}</code>
⏱️ <b>Time:</b> {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
━━━━━━━━━━━━━━━━━━
💡 <b>How to receive alerts:</b>
• <b>Personal Alerts:</b> Copy your User ID <code>{chat_id}</code> and paste it in Admin Dashboard -> Settings.
• <b>Group Alerts:</b> Add me to your Telegram Group and type <code>/connect &lt;merchant_code&gt;</code>.

✅ <i>Engine is ready and listening for transactions!</i>
"""
                        await send_raw_telegram_message(bot_token, chat_id, dm_welcome.strip())
                        continue
                    elif cmd in ["/help", "/status", "/info"]:
                        info_msg = f"""
ℹ️ <b>ABA PayWay Bot Status / ព័ត៌មានប្រព័ន្ធ</b>
━━━━━━━━━━━━━━━━━━
🤖 <b>Bot:</b> {bot_name} (@{bot_username})
💬 <b>This Chat ID:</b> <code>{chat_id}</code>
👥 <b>Chat Title:</b> {chat_title}
⏱️ <b>Server Time:</b> {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
━━━━━━━━━━━━━━━━━━
💡 <b>Commands:</b>
• <code>/connect &lt;merchant_code&gt;</code> - Link this chat to a merchant
• <code>/status</code> - Check connection info
"""
                        await send_raw_telegram_message(bot_token, chat_id, info_msg.strip())
                        continue

                if not target_merchant_code:
                    continue

                # Query database for merchant with target_merchant_code
                async with async_session() as db:
                    m_res = await db.execute(select(Merchant).where(Merchant.code_merchant == target_merchant_code))
                    merchant = m_res.scalar_one_or_none()

                    if merchant:
                        # Append chat_id if not already linked
                        existing_ids = parse_chat_ids(merchant.telegram_chat_id)
                        if chat_id not in existing_ids:
                            existing_ids.append(chat_id)
                            new_chat_id_str = ", ".join(existing_ids)
                            
                            merchant.telegram_chat_id = new_chat_id_str
                            await db.commit()
                            print(f"LOG: [Telegram] Auto-connected Chat {chat_id} ({chat_title}) to Merchant '{target_merchant_code}'")

                        # Send success confirmation & verification in Telegram group
                        confirm_msg = f"""
🎉 <b>ភ្ជាប់ដោយជោគជ័យ! / Connected & Verified!</b>
━━━━━━━━━━━━━━━━━━
🏪 <b>Merchant:</b> <b>{merchant.name}</b> (<code>{merchant.code_merchant}</code>)
👥 <b>Group / Chat:</b> {chat_title}
💬 <b>Chat ID:</b> <code>{chat_id}</code>
⏱️ <b>Verified At:</b> {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
━━━━━━━━━━━━━━━━━━
✅ <b>Status:</b> 🟢 <b>ACTIVE & OPERATIONAL</b>
🔔 <i>ក្រុម Telegram នេះនឹងទទួលបានការជូនដំណឹងពីការទូទាត់ភ្លាមៗ! (All payments for this merchant will notify here in real-time).</i>
"""
                        await send_raw_telegram_message(bot_token, chat_id, confirm_msg.strip())

                        connected_events.append({
                            "code_merchant": target_merchant_code,
                            "merchant_name": merchant.name,
                            "chat_id": chat_id,
                            "chat_title": chat_title
                        })
                    else:
                        not_found_msg = f"""
⚠️ <b>រកមិនឃើញ Merchant / Merchant Not Found</b>
━━━━━━━━━━━━━━━━━━
❌ រកមិនឃើញ Merchant ដែលមានកូដ: <code>{target_merchant_code}</code> នៅក្នុងប្រព័ន្ធទេ។
💡 សូមពិនិត្យមើល Merchant Code ក្នុង Admin Dashboard រួចសាកល្បងម្តងទៀត ឧទាហរណ៍៖ <code>/connect &lt;code_merchant&gt;</code>
"""
                        await send_raw_telegram_message(bot_token, chat_id, not_found_msg.strip())

            return {"ok": True, "connected": connected_events}
    except Exception as e:
        return {"ok": False, "error": f"Auto-connect error: {str(e)}"}

async def start_telegram_poller():
    """Background worker that continuously polls for Telegram auto-connect commands."""
    print("LOG: [Telegram] Background auto-connect listener started.")
    while True:
        try:
            enabled = await get_setting_value("telegram_enabled", "false")
            if enabled.lower() == "true":
                bot_token = await get_setting_value("telegram_bot_token")
                if bot_token:
                    await process_telegram_auto_connect(bot_token)
        except Exception as e:
            pass
        await asyncio.sleep(4.0)

async def get_telegram_bot_info(bot_token: str) -> Dict[str, Any]:
    """Fetches Telegram bot profile to verify token validity."""
    if not bot_token:
        return {"ok": False, "error": "Bot token is required"}

    url = f"{TELEGRAM_API_BASE}/bot{bot_token}/getMe"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.get(url)
            data = res.json()
            if data.get("ok"):
                result = data.get("result", {})
                return {
                    "ok": True,
                    "id": result.get("id"),
                    "first_name": result.get("first_name"),
                    "username": result.get("username"),
                    "can_join_groups": result.get("can_join_groups", True)
                }
            return {"ok": False, "error": data.get("description", "Invalid Bot Token")}
    except Exception as e:
        return {"ok": False, "error": f"Connection error: {str(e)}"}

async def fetch_telegram_recent_chats(bot_token: str) -> Dict[str, Any]:
    """
    Fetches recent updates from Telegram to automatically detect
    all unique Groups, Supergroups, Channels, and Private chats where the bot received messages.
    """
    if not bot_token:
        return {"ok": False, "error": "Bot token is required"}

    # First verify bot
    bot_info = await get_telegram_bot_info(bot_token)
    if not bot_info.get("ok"):
        return bot_info

    url = f"{TELEGRAM_API_BASE}/bot{bot_token}/getUpdates"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.get(url, params={"limit": 100})
            data = res.json()
            if not data.get("ok"):
                return {"ok": False, "error": data.get("description", "Failed to fetch updates")}

            bot_id = bot_info.get("id")
            raw_updates = data.get("result", [])
            chats_dict: Dict[int, Dict[str, Any]] = {}

            for update in raw_updates:
                # Extract chat object from message, edited_message, channel_post, or my_chat_member
                msg = (
                    update.get("message") or 
                    update.get("edited_message") or 
                    update.get("channel_post") or 
                    update.get("my_chat_member")
                )
                if not msg:
                    continue

                chat = msg.get("chat")
                if not chat:
                    continue

                chat_id = chat.get("id")
                chat_type = chat.get("type", "unknown")

                # Skip the bot's own ID and other bots
                if bot_id and chat_id == bot_id:
                    continue
                if chat.get("is_bot") or msg.get("from", {}).get("is_bot"):
                    if chat_type == "private":
                        continue
                
                # Format friendly title
                if chat_type in ["group", "supergroup", "channel"]:
                    title = chat.get("title") or f"Group ({chat_id})"
                else:
                    first_name = chat.get("first_name", "")
                    last_name = chat.get("last_name", "")
                    full_name = f"{first_name} {last_name}".strip()
                    username = chat.get("username")
                    title = f"{full_name} (@{username})" if username else (full_name or f"User ({chat_id})")

                username = chat.get("username")
                
                chats_dict[chat_id] = {
                    "chat_id": str(chat_id),
                    "title": title,
                    "type": chat_type,
                    "username": username,
                    "date": msg.get("date")
                }

            chat_list = list(chats_dict.values())
            # Sort by date descending (newest first)
            chat_list.sort(key=lambda x: x.get("date") or 0, reverse=True)

            return {
                "ok": True,
                "bot": bot_info,
                "chats": chat_list,
                "count": len(chat_list)
            }
    except Exception as e:
        return {"ok": False, "error": f"Error querying Telegram: {str(e)}"}

async def send_raw_telegram_message(bot_token: str, chat_id: str, text_html: str) -> Dict[str, Any]:
    """Sends a raw HTML-formatted Telegram message."""
    if not bot_token or not chat_id:
        return {"ok": False, "error": "Bot token and Chat ID are required"}

    # Validate if user passed bot's own token ID prefix
    token_bot_id = bot_token.split(":")[0] if ":" in bot_token else None
    if token_bot_id and str(chat_id).strip() == token_bot_id:
        return {
            "ok": False,
            "error": "អ្នកបានដាក់លេខ Bot ID ខ្លួនឯង។ សូមផ្ញើសារ /start ទៅកាន់ Bot របស់អ្នកពីគណនី Telegram ផ្ទាល់ខ្លួន ឬ Add Bot ចូល Group រួចវាយសារមួយដើម្បីឱ្យប្រព័ន្ធចាប់យក Chat ID ត្រឹមត្រូវ។ (Cannot send messages to the bot itself. Please use your personal User ID or Group ID)."
        }

    url = f"{TELEGRAM_API_BASE}/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text_html,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.post(url, json=payload)
            data = res.json()
            if data.get("ok"):
                return {"ok": True, "message_id": data.get("result", {}).get("message_id")}
            err_desc = data.get("description", "Failed to send message")
            if "can't send messages to the bot" in err_desc.lower():
                err_desc = "អ្នកបានដាក់លេខ Bot ID ខ្លួនឯង។ សូមផ្ញើសារទៅកាន់ Bot ពីគណនីរបស់អ្នក ឬ Add Bot ចូល Group រួចចុច 'Fetch & Detect Chats'។ (The bot cannot send messages to itself. Please enter your User ID or Group ID)."
            return {"ok": False, "error": err_desc}
    except Exception as e:
        return {"ok": False, "error": f"Network error sending telegram message: {str(e)}"}

def parse_chat_ids(raw_input: Any) -> List[str]:
    """Parses a comma, space, or newline-separated string/list into a clean unique list of chat IDs."""
    if not raw_input:
        return []
    if isinstance(raw_input, list):
        items = raw_input
    else:
        # Replace newlines and semicolons with commas
        cleaned = str(raw_input).replace('\n', ',').replace(';', ',')
        items = cleaned.split(',')
    
    unique_ids = []
    for item in items:
        cid = str(item).strip()
        if cid and cid not in unique_ids:
            unique_ids.append(cid)
    return unique_ids

async def broadcast_telegram_message(bot_token: str, chat_ids: Any, text_html: str) -> List[Dict[str, Any]]:
    """Broadcasts an HTML message to multiple Telegram chats / groups concurrently."""
    targets = parse_chat_ids(chat_ids)
    if not bot_token or not targets:
        return [{"ok": False, "error": "Bot token and at least one Chat ID are required"}]

    tasks = [send_raw_telegram_message(bot_token, cid, text_html) for cid in targets]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    formatted_results = []
    for cid, res in zip(targets, results):
        if isinstance(res, Exception):
            formatted_results.append({"chat_id": cid, "ok": False, "error": str(res)})
        else:
            formatted_results.append({"chat_id": cid, **res})
    return formatted_results

async def send_test_telegram_message(bot_token: str, chat_id: str) -> Dict[str, Any]:
    """Sends an interactive test alert to verify Telegram integration (supports multiple IDs)."""
    bot_info = await get_telegram_bot_info(bot_token)
    bot_name = bot_info.get("first_name", "ABA PayWay Bot") if bot_info.get("ok") else "ABA PayWay Bot"
    bot_user = f"@{bot_info.get('username')}" if bot_info.get("username") else "Connected"

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    targets = parse_chat_ids(chat_id)
    if not targets:
        return {"ok": False, "error": "Please enter a valid Chat ID or Group ID."}

    msg = f"""
🤖 <b>Telegram Alert Test / សាកល្បងការតភ្ជាប់</b>
━━━━━━━━━━━━━━━━━━
✅ <b>Status:</b> Connected & Operational
👑 <b>Bot:</b> {bot_name} ({bot_user})
💬 <b>Target Chats:</b> <code>{', '.join(targets)}</code>
⏱️ <b>Time:</b> {now_str}
━━━━━━━━━━━━━━━━━━
🔔 <i>You will receive instant payment alerts here!</i>
"""
    results = await broadcast_telegram_message(bot_token, targets, msg.strip())
    # If at least one succeeded, return ok
    successes = [r for r in results if r.get("ok")]
    if successes:
        return {"ok": True, "delivered_count": len(successes), "total_targets": len(targets)}
    # If all failed, return the first error
    return {"ok": False, "error": results[0].get("error", "Failed to send test message")}

async def send_payment_success_alert(order_data: Dict[str, Any]):
    """
    Sends automated payment success alert when an order is verified.
    Supports per-merchant custom group routing + multi-group broadcasting.
    """
    try:
        enabled = await get_setting_value("telegram_enabled", "false")
        if enabled.lower() != "true":
            return

        bot_token = await get_setting_value("telegram_bot_token")
        global_chat_id = await get_setting_value("telegram_chat_id")

        if not bot_token:
            return

        code_merchant = order_data.get("code_merchant")
        merchant_chat_id = ""

        # Check if merchant has custom telegram_chat_id configured
        if code_merchant:
            from model.merchant import Merchant
            async with async_session() as db:
                m_res = await db.execute(select(Merchant).where(Merchant.code_merchant == code_merchant))
                merchant = m_res.scalar_one_or_none()
                if merchant and merchant.telegram_chat_id:
                    merchant_chat_id = merchant.telegram_chat_id

        # Resolve target chats: use merchant-specific chats, and optionally global chats
        target_chat_ids = parse_chat_ids(merchant_chat_id)
        if not target_chat_ids:
            target_chat_ids = parse_chat_ids(global_chat_id)
        elif global_chat_id:
            # Also include global chat if not already present
            for gid in parse_chat_ids(global_chat_id):
                if gid not in target_chat_ids:
                    target_chat_ids.append(gid)

        if not target_chat_ids:
            return

        order_id = order_data.get("id", "N/A")
        amount = order_data.get("amount", "0.00")
        currency = order_data.get("currency", "USD").upper()
        merchant_name = order_data.get("merchant_name") or order_data.get("code_merchant") or "Default Store"
        tran_id = order_data.get("tran_id") or "N/A"
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        currency_symbol = "$" if currency == "USD" else "៛"

        msg = f"""
🎉 <b>ការទូទាត់ទទួលបានជោគជ័យ! / Payment Verified!</b>
━━━━━━━━━━━━━━━━━━
🏪 <b>Merchant:</b> {merchant_name}
💵 <b>Amount:</b> <b>{currency_symbol}{amount} {currency}</b>
🧾 <b>Invoice ID:</b> <code>#{order_id}</code>
🆔 <b>Transaction ID:</b> <code>{tran_id}</code>
⏱️ <b>Time:</b> {now_str}
━━━━━━━━━━━━━━━━━━
✅ <i>Verified by ABA PayWay Engine</i>
"""
        await broadcast_telegram_message(bot_token, target_chat_ids, msg.strip())
    except Exception as e:
        print(f"LOG: [Telegram] Failed to send payment alert: {e}")

async def send_order_created_alert(order_data: Dict[str, Any]):
    """Sends optional notification when a new checkout invoice is created."""
    try:
        enabled = await get_setting_value("telegram_enabled", "false")
        notify_create = await get_setting_value("telegram_notify_create", "false")
        
        if enabled.lower() != "true" or notify_create.lower() != "true":
            return

        bot_token = await get_setting_value("telegram_bot_token")
        global_chat_id = await get_setting_value("telegram_chat_id")

        if not bot_token:
            return

        code_merchant = order_data.get("code_merchant")
        merchant_chat_id = ""

        if code_merchant:
            from model.merchant import Merchant
            async with async_session() as db:
                m_res = await db.execute(select(Merchant).where(Merchant.code_merchant == code_merchant))
                merchant = m_res.scalar_one_or_none()
                if merchant and merchant.telegram_chat_id:
                    merchant_chat_id = merchant.telegram_chat_id

        target_chat_ids = parse_chat_ids(merchant_chat_id) or parse_chat_ids(global_chat_id)
        if not target_chat_ids:
            return

        order_id = order_data.get("id", "N/A")
        amount = order_data.get("amount", "0.00")
        currency = order_data.get("currency", "USD").upper()
        merchant_code = order_data.get("code_merchant", "N/A")
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        msg = f"""
🧾 <b>វិក្កយបត្រថ្មីត្រូវបានបង្កើត / New Invoice Created</b>
━━━━━━━━━━━━━━━━━━
🏪 <b>Merchant Code:</b> <code>{merchant_code}</code>
💵 <b>Amount:</b> {amount} {currency}
🧾 <b>Invoice ID:</b> <code>#{order_id}</code>
⏱️ <b>Time:</b> {now_str}
⏳ <b>Status:</b> <i>Waiting for Customer Scan...</i>
━━━━━━━━━━━━━━━━━━
"""
        await broadcast_telegram_message(bot_token, target_chat_ids, msg.strip())
    except Exception as e:
        print(f"LOG: [Telegram] Failed to send order creation alert: {e}")
