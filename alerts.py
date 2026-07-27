import os
import urllib.request
import urllib.parse
import json

# Integration Tokens can be set in GitHub secrets or Cloud environment variables
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
WHATSAPP_API_KEY = os.environ.get("WHATSAPP_API_KEY", "") # e.g., Twilio or Ultramsg

def send_telegram_alert(chat_id, message):
    """
    Sends real-time price notification alert directly to a Telegram User/Channel.
    Uses official Telegram Bot API. Fully free and robust.
    """
    if not TELEGRAM_BOT_TOKEN:
        print(f"Telegram Bot Token not configured. Mocking alert to Chat ID {chat_id}: {message}")
        return True
        
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML"
    }
    
    try:
        data = urllib.parse.urlencode(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, method="POST")
        with urllib.request.urlopen(req, timeout=8) as res:
            res_data = json.loads(res.read().decode())
            return res_data.get("ok", False)
    except Exception as e:
        print(f"Error sending real Telegram alert: {e}")
        return False

def send_whatsapp_alert(phone_number, message):
    """
    Sends price alert via WhatsApp API (e.g. using Twilio, Ultramsg, or Chat-API).
    Since WhatsApp is a paid service, if API key is absent, we log and mock it.
    """
    if not WHATSAPP_API_KEY:
        print(f"WhatsApp API Key not configured. Mocking alert to +91{phone_number}: {message}")
        return True
        
    # Example Ultramsg Integration
    url = "https://api.ultramsg.com/instance1234/messages/chat"
    payload = {
        "token": WHATSAPP_API_KEY,
        "to": f"+91{phone_number}" if not phone_number.startswith("+") else phone_number,
        "body": message
    }
    
    try:
        data = urllib.parse.urlencode(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, method="POST")
        with urllib.request.urlopen(req, timeout=8) as res:
            return True
    except Exception as e:
        print(f"Error sending real WhatsApp alert: {e}")
        return False

def broadcast_price_alerts(records, subscriptions):
    """
    Broadcasts daily mandi prices to active subscribers on WhatsApp & Telegram.
    Matches subscriber filters (district & crop).
    """
    success_count = 0
    
    for sub in subscriptions:
        if not sub.is_active:
            continue
            
        # Filter records matching subscriber preference
        relevant = [
            r for r in records 
            if (sub.district == "all" or r.district.lower() == sub.district.lower())
            and (sub.commodity == "all" or r.commodity.lower() == sub.commodity.lower())
        ]
        
        if not relevant:
            continue
            
        # Construct attractive message
        msg_header = f"🌾 <b>UP Mandi Live Price Alert</b> 🌾\n"
        msg_header += f"Vijay Kumar Traders — Daily Rates Update\n"
        msg_header += "━━━━━━━━━━━━━━━━━━━━━━\n"
        
        msg_body = ""
        for r in relevant[:5]: # Send top 5 relevant prices to keep it clean
            msg_body += f"📍 <b>{r.mandi_hi}</b>\n"
            msg_body += f"🔸 {r.commodity_hi} ({r.variety_hi}): <b>₹{r.modal_price}/Q</b>\n"
            msg_body += f"📊 भाव रेंज: ₹{r.min_price} - ₹{r.max_price}\n\n"
            
        msg_footer = "━━━━━━━━━━━━━━━━━━━━━━\n"
        msg_footer += "🔗 और भाव देखें: https://abhishekagrahari307-max.github.io/mandi/"
        
        full_message = msg_header + msg_body + msg_footer
        
        # Route to WhatsApp or Telegram
        if sub.contact_type == "telegram":
            ok = send_telegram_alert(sub.contact_value, full_message)
            if ok: success_count += 1
        elif sub.contact_type == "whatsapp":
            ok = send_whatsapp_alert(sub.contact_value, full_message)
            if ok: success_count += 1
            
    return success_count
