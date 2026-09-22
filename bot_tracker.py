import requests
import json
import time
import os
from datetime import datetime

TELEGRAM_TOKEN = "8538685611:AAFdtX2yn_dhwCB7q1l4zZu8ALohjEqKGIA"
CHAT_ID = "2095107561"
SOLANA_RPC = "https://api.mainnet-beta.solana.com"
WALLETS_FILE = "wallets.json"
STATS_FILE = "stats.json"

BASE_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

# Known DEX Program IDs
RAYDIUM_AMM = "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8"
PUMP_FUN_PROGRAM = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"

def load_json(filename, default_val):
    if os.path.exists(filename):
        with open(filename, "r") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return default_val
    return default_val

def save_json(filename, data):
    with open(filename, "w") as f:
        json.dump(data, f, indent=4)

tracked_wallets = load_load_wallets = load_json(WALLETS_FILE, ["675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8"])
# Fix helper definition reference
tracked_wallets = load_json(WALLETS_FILE, ["675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8"])

# Initialize stats structure
default_stats = {
    "total_trades": 0,
    "total_buys": 0,
    "total_sells": 0,
    "total_sol_volume": 0.0,
    "dex_breakdown": {"Raydium ⚡": 0, "Pump.fun 💊": 0, "Unknown DEX": 0}
}
stats = load_json(STATS_FILE, default_stats)

seen_signatures = set()
last_update_id = 0

def save_wallets(wallets):
    save_json(WALLETS_FILE, wallets)

def save_stats():
    save_json(STATS_FILE, stats)

def send_telegram_alert(message):
    url = f"{BASE_URL}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown", "disable_web_page_preview": True}
    try:
        res = requests.post(url, json=payload, timeout=15)
        res.raise_for_status()
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S' )}] Telegram send error: {e}")

def parse_transaction_details(signature):
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getTransaction",
        "params": [
            signature,
            {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}
        ]
    }
    headers = {"Content-Type": "application/json"}
    try:
        res = requests.post(SOLANA_RPC, json=payload, headers=headers, timeout=15)
        res.raise_for_status()
        tx_data = res.json().get("result")
        if not tx_data:
            return None

        account_keys = [
            acc.get("pubkey") if isinstance(acc, dict) else acc 
            for acc in tx_data.get("transaction", {}).get("message", {}).get("accountKeys", [])
        ]
        
        dex = "Unknown DEX"
        if PUMP_FUN_PROGRAM in account_keys:
            dex = "Pump.fun 💊"
        elif RAYDIUM_AMM in account_keys:
            dex = "Raydium ⚡"

        meta = tx_data.get("meta", {})
        pre_balances = meta.get("preBalances", [])
        post_balances = meta.get("postBalances", [])
        sol_change = 0
        if pre_balances and post_balances:
            sol_change = (post_balances[0] - pre_balances[0]) / 1e9

        post_token_balances = meta.get("postTokenBalances", [])
        token_mint = "SOL / Token"
        for token_info in post_token_balances:
            mint = token_info.get("mint")
            if mint and mint != "So11111111111111111111111111111111111111112":
                token_mint = mint
                break

        trade_type = "BUY 🟢" if sol_change < 0 else "SELL 🔴" if sol_change > 0 else "SWAP 🔄"
        
        return {
            "dex": dex,
            "trade_type": trade_type,
            "sol_amount": abs(round(sol_change, 4)),
            "token_mint": token_mint
        }
    except Exception as e:
        print(f"Error parsing transaction {signature[:8]}: {e}")
        return None

def handle_commands():
    global last_update_id, tracked_wallets
    url = f"{BASE_URL}/getUpdates"
    params = {"offset": last_update_id + 1, "timeout": 2}
    
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

            elif text == "/stats":
                raydium_count = stats["dex_breakdown"].get("Raydium ⚡", 0)
                pump_count = stats["dex_breakdown"].get("Pump.fun 💊", 0)
                unknown_count = stats["dex_breakdown"].get("Unknown DEX", 0)
                
                stats_msg = (
                    f"📊 *SOLANA TRACKER ANALYTICS*\n\n"
                    f"• *Total Trades Captured*: `{stats['total_trades']}`\n"
                    f"• *Total Buys*: `{stats['total_buys']} 🟢`\n"
                    f"• *Total Sells*: `{stats['total_sells']} 🔴`\n"
                    f"• *Total SOL Volume*: `{round(stats['total_sol_volume'], 2)} SOL`\n\n"
                    f"*DEX Distribution*:\n"
                    f"  - Raydium: `{raydium_count}`\n"
                    f"  - Pump.fun: `{pump_count}`\n"
                    f"  - Other/Unknown: `{unknown_count}`"
                )
                send_telegram_alert(stats_msg)
                    
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Network retry on command check: {e}")

def check_wallet_activity():
    global stats
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
                    
                    details = parse_transaction_details(sig)
                    
                    if details:
                        # Update analytics counters
                        stats["total_trades"] += 1
                        if "BUY" in details["trade_type"]:
                            stats["total_buys"] += 1
                        elif "SELL" in details["trade_type"]:
                            stats["total_sells"] += 1
                        
                        stats["total_sol_volume"] += details["sol_amount"]
                        
                        dex_key = details["dex"]
                        if dex_key in stats["dex_breakdown"]:
                            stats["dex_breakdown"][dex_key] += 1
                        else:
                            stats["dex_breakdown"]["Unknown DEX"] += 1
                            
                        save_stats()

                        msg = (
                            f"🚨 *WHALE {details['trade_type']} DETECTED*\n\n"
                            f"• *Platform*: `{details['dex']}`\n"
                            f"• *Wallet*: `{wallet[:6]}...{wallet[-4:]}`\n"
                            f"• *Amount*: `{details['sol_amount']} SOL`\n"
                            f"• *Token Mint*: `{details['token_mint']}`\n"
                            f"• *Status*: {status}\n"
                            f"• *Links*: [Solscan](https://solscan.io/tx/{sig}) | [DexScreener](https://dexscreener.com/solana/{details['token_mint']})"
                        )
                    else:
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
    print("Starting Advanced Solana DEX Tracker with Analytics...")
    send_telegram_alert("⚡ *Analytics Engine Active.*\n\nNew Commands:\n• `/stats` - View aggregate trading metrics\n• `/add` / `/remove` / `/list`")
    
    while True:
        try:
            handle_commands()
            check_wallet_activity()
        except Exception as main_e:
            print(f"Main loop recovered from error: {main_e}")
        time.sleep(5)
