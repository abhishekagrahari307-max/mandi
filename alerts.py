import json
import os
import urllib.parse
import urllib.request


TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
WHATSAPP_API_KEY = os.environ.get("WHATSAPP_API_KEY", "").strip()
WHATSAPP_API_URL = os.environ.get("WHATSAPP_API_URL", "").strip()


def send_telegram_alert(chat_id, message):
    """Send through Telegram Bot API; return False when not configured."""
    if not TELEGRAM_BOT_TOKEN:
        print("Telegram alert skipped: TELEGRAM_BOT_TOKEN is not configured")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "HTML"}
    try:
        data = urllib.parse.urlencode(payload).encode("utf-8")
        request = urllib.request.Request(url, data=data, method="POST")
        with urllib.request.urlopen(request, timeout=8) as response:
            response_data = json.loads(response.read().decode())
            return bool(response_data.get("ok"))
    except Exception as exc:
        print(f"Error sending Telegram alert: {exc}")
        return False


def send_whatsapp_alert(phone_number, message):
    """Send through a configured provider endpoint; never report a mock send."""
    if not WHATSAPP_API_KEY or not WHATSAPP_API_URL:
        print("WhatsApp alert skipped: WHATSAPP_API_URL/API key is not configured")
        return False

    destination = phone_number if phone_number.startswith("+") else f"+91{phone_number}"
    payload = json.dumps({"to": destination, "message": message}).encode("utf-8")
    request = urllib.request.Request(
        WHATSAPP_API_URL,
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Bearer {WHATSAPP_API_KEY}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            return 200 <= response.status < 300
    except Exception as exc:
        print(f"Error sending WhatsApp alert: {exc}")
        return False


def broadcast_price_alerts(records, subscriptions):
    """Broadcast verified database rates and count only actual provider sends."""
    success_count = 0
    for subscription in subscriptions:
        if not subscription.is_active:
            continue
        relevant = [
            record for record in records
            if (subscription.district == "all" or record.district.lower() == subscription.district.lower())
            and (subscription.commodity == "all" or record.commodity.lower() == subscription.commodity.lower())
        ]
        if not relevant:
            continue

        message = "🌾 <b>UP Mandi Price Alert</b> 🌾\n"
        message += "Vijay Kumar Traders — Verified Rate Update\n"
        message += "━━━━━━━━━━━━━━━━━━━━━━\n"
        for record in relevant[:5]:
            message += f"📍 <b>{record.mandi_hi}</b>\n"
            message += f"🔸 {record.commodity_hi} ({record.variety_hi}): <b>₹{record.modal_price}/Q</b>\n"
            message += f"📊 भाव रेंज: ₹{record.min_price} - ₹{record.max_price}\n\n"
        message += "━━━━━━━━━━━━━━━━━━━━━━\n"
        message += "🔗 https://abhishekagrahari307-max.github.io/mandi/"

        sent = False
        if subscription.contact_type == "telegram":
            sent = send_telegram_alert(subscription.contact_value, message)
        elif subscription.contact_type == "whatsapp":
            sent = send_whatsapp_alert(subscription.contact_value, message)
        if sent:
            success_count += 1
    return success_count
