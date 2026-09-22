import requests
import time
from datetime import datetime

TELEGRAM_TOKEN = "8538685611:AAFdtX2yn_dhwCB7q1l4zZu8ALohjEqKGIA"
CHAT_ID = "2095107561"
SOLANA_RPC = "https://api.mainnet-beta.solana.com"
TARGET_WALLET = "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8"

seen_signatures = set()

def send_telegram_alert(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        res = requests.post(url, json=payload, timeout=10)
        res.raise_for_status()
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Telegram alert sent!")
    except Exception as e:
        print(f"Error sending alert: {e}")

def check_wallet_activity():
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getSignaturesForAddress",
        "params": [TARGET_WALLET, {"limit": 3}]
    }
    headers = {"Content-Type": "application/json"}
    
    try:
        res = requests.post(SOLANA_RPC, json=payload, headers=headers, timeout=10)
        res.raise_for_status()
        signatures = res.json().get("result", [])
        
        for tx in reversed(signatures):
            sig = tx.get("signature")
            if sig not in seen_signatures:
                seen_signatures.add(sig)
                status = "❌ Failed" if tx.get("err") else "✅ Success"
                slot = tx.get("slot")
                
                msg = (
                    f"🚨 *SMART MONEY ACTIVITY DETECTED*\n\n"
                    f"• *Wallet*: `{TARGET_WALLET[:6]}...{TARGET_WALLET[-4:]}`\n"
                    f"• *Status*: {status}\n"
                    f"• *Slot*: `{slot}`\n"
                    f"• *Explorer*: [View on Solscan](https://solscan.io/tx/{sig})"
                )
                send_telegram_alert(msg)
                
    except Exception as e:
        print(f"Error checking wallet: {e}")

if __name__ == "__main__":
    print("Starting Solana Smart Money Telegram Alert Loop...")
    send_telegram_alert("⚡ *Solana Smart Money Tracker is active and monitoring.*")
    
    while True:
        check_wallet_activity()
        time.sleep(15)
