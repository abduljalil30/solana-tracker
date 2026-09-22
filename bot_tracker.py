import requests
import json
import time
import os
from datetime import datetime

TELEGRAM_TOKEN = "8538685611:AAFdtX2yn_dhwCB7q1l4zZu8ALohjEqKGIA"
CHAT_ID = "2095107561"
SOLANA_RPC = "https://api.mainnet-beta.solana.com"
WALLETS_FILE = "wallets.json"

BASE_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

def load_wallets():
    if os.path.exists(WALLETS_FILE):
        with open(WALLETS_FILE, "r") as f:
            return json.load(f)
    return ["675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8"]

def save_wallets(wallets):
    with open(WALLETS_FILE, "w") as f:
        json.dump(wallets, f, indent=4)

tracked_wallets = load_wallets()
seen_signatures = set()
last_update_id = 0

def send_telegram_alert(message):
    url = f"{BASE_URL}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        res = requests.post(url, json=payload, timeout=15)
        res.raise_for_status()
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Telegram send timeout/error: {e}")

def handle_commands():
    global last_update_id, tracked_wallets
    url = f"{BASE_URL}/getUpdates"
    params = {"offset": last_update_id + 1, "timeout": 5}
    
    try:
        res = requests.get(url, params=params, timeout=10)
        if res.status_code == 409:
            time.sleep(3)
            return
        res.raise_for_status()
        updates = res.json().get("result", [])
        
        for update in updates:
            last_update_id = update["update_id"]
            message = update.get("message", {})
            text = message.get("text", "").strip()
            
            if not text:
                continue
                
            if text.startswith("/add"):
                parts = text.split()
                if len(parts) > 1:
                    new_wallet = parts[1]
                    if new_wallet not in tracked_wallets:
                        tracked_wallets.append(new_wallet)
                        save_wallets(tracked_wallets)
                        send_telegram_alert(f"✅ *Added Wallet:* `{new_wallet[:6]}...{new_wallet[-4:]}`")
                    else:
                        send_telegram_alert("⚠️ *Wallet is already being tracked.*")
                else:
                    send_telegram_alert("Usage: `/add <solana_address>`")
                    
            elif text.startswith("/remove"):
                parts = text.split()
                if len(parts) > 1:
                    target = parts[1]
                    if target in tracked_wallets:
                        tracked_wallets.remove(target)
                        save_wallets(tracked_wallets)
                        send_telegram_alert(f"🗑 *Removed Wallet:* `{target[:6]}...{target[-4:]}`")
                    else:
                        send_telegram_alert("⚠️ *Wallet not found in track list.*")
                else:
                    send_telegram_alert("Usage: `/remove <solana_address>`")
                    
            elif text == "/list":
                if tracked_wallets:
                    wallet_list = "\n".join([f"• `{w[:6]}...{w[-4:]}`" for w in tracked_wallets])
                    send_telegram_alert(f"📋 *Tracked Wallets ({len(tracked_wallets)}):*\n\n{wallet_list}")
                else:
                    send_telegram_alert("📋 *No wallets currently tracked.*")
                    
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Network retry on command check: {e}")

def check_wallet_activity():
    headers = {"Content-Type": "application/json"}
    
    for wallet in tracked_wallets:
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getSignaturesForAddress",
            "params": [wallet, {"limit": 2}]
        }
        try:
            res = requests.post(SOLANA_RPC, json=payload, headers=headers, timeout=15)
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
                        f"• *Wallet*: `{wallet[:6]}...{wallet[-4:]}`\n"
                        f"• *Status*: {status}\n"
                        f"• *Slot*: `{slot}`\n"
                        f"• *Explorer*: [View on Solscan](https://solscan.io/tx/{sig})"
                    )
                    send_telegram_alert(msg)
                    
        except Exception as e:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Solana RPC retry for {wallet[:6]}: {e}")

if __name__ == "__main__":
    print("Starting Interactive Solana Tracker Engine...")
    send_telegram_alert("⚡ *Interactive Solana Tracker Online.*\n\nCommands:\n• `/add <address>`\n• `/remove <address>`\n• `/list`")
    
    while True:
        try:
            handle_commands()
            check_wallet_activity()
        except Exception as main_e:
            print(f"Main loop recovered from error: {main_e}")
        time.sleep(5)
