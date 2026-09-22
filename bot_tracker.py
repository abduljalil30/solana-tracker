import requests
import json
import time
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
SOLANA_RPC = "https://api.mainnet-beta.solana.com"
WALLETS_FILE = "wallets.json"
STATS_FILE = "stats.json"

BASE_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

# Known DEX Program IDs
RAYDIUM_AMM = "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8"
PUMP_FUN_PROGRAM = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"

def load_wallets_file():
    if os.path.exists(WALLETS_FILE):
        with open(WALLETS_FILE, "r") as f:
            try:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
            except json.JSONDecodeError:
                pass
    return {}

def load_stats_file():
    default_stats = {
        "total_trades": 0,
        "total_buys": 0,
        "total_sells": 0,
        "total_sol_volume": 0.0,
        "dex_breakdown": {"Raydium ⚡": 0, "Pump.fun 💊": 0, "Unknown DEX": 0}
    }
    if os.path.exists(STATS_FILE):
        with open(STATS_FILE, "r") as f:
            try:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
            except json.JSONDecodeError:
                pass
    return default_stats

# Structure: { "chat_id": { "wallet_address": "last_known_signature" } }
user_wallets = load_wallets_file()
stats = load_stats_file()
last_update_id = 0

def save_wallets():
    with open(WALLETS_FILE, "w") as f:
        json.dump(user_wallets, f, indent=4)

def save_stats():
    with open(STATS_FILE, "w") as f:
        json.dump(stats, f, indent=4)

def send_telegram_alert(chat_id, message):
    url = f"{BASE_URL}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown", "disable_web_page_preview": True}
    try:
        res = requests.post(url, json=payload, timeout=15)
        res.raise_for_status()
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Telegram send error to {chat_id}: {e}")

def get_latest_signature(wallet):
    """Fetches the absolute latest signature for a wallet to use as a baseline."""
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getSignaturesForAddress",
        "params": [wallet, {"limit": 1}]
    }
    headers = {"Content-Type": "application/json"}
    try:
        res = requests.post(SOLANA_RPC, json=payload, headers=headers, timeout=15)
        res.raise_for_status()
        signatures = res.json().get("result", [])
        if signatures:
            return signatures[0].get("signature")
    except Exception as e:
        print(f"Error fetching latest signature for {wallet}: {e}")
    return None

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
    global last_update_id, user_wallets
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
            chat_id = str(message.get("chat", {}).get("id"))
            text = message.get("text", "").strip()
            
            if not chat_id or not text:
                continue
                
            if chat_id not in user_wallets:
                user_wallets[chat_id] = {}
                
            # Backward compatibility check if user_wallets[chat_id] is a list
            if isinstance(user_wallets[chat_id], list):
                old_list = user_wallets[chat_id]
                user_wallets[chat_id] = {}
                for w in old_list:
                    user_wallets[chat_id][w] = get_latest_signature(w)
                save_wallets()
                
            if text.startswith("/add"):
                parts = text.split()
                if len(parts) > 1:
                    new_wallet = parts[1]
                    if new_wallet not in user_wallets[chat_id]:
                        # Get latest sig so we ignore historical trades
                        latest_sig = get_latest_signature(new_wallet)
                        user_wallets[chat_id][new_wallet] = latest_sig
                        save_wallets()
                        send_telegram_alert(chat_id, f"✅ *Added Wallet & Synced:* `{new_wallet[:6]}...{new_wallet[-4:]}`\n_Watching for future trades only._")
                    else:
                        send_telegram_alert(chat_id, "⚠️ *Wallet is already in your tracking list.*")
                else:
                    send_telegram_alert(chat_id, "Usage: `/add <solana_address>`")
                    
            elif text.startswith("/remove"):
                parts = text.split()
                if len(parts) > 1:
                    target = parts[1]
                    if target in user_wallets[chat_id]:
                        del user_wallets[chat_id][target]
                        save_wallets()
                        send_telegram_alert(chat_id, f"🗑 *Removed Wallet:* `{target[:6]}...{target[-4:]}`")
                    else:
                        send_telegram_alert(chat_id, "⚠️ *Wallet not found in your tracking list.*")
                else:
                    send_telegram_alert(chat_id, "Usage: `/remove <solana_address>`")
                    
            elif text == "/list":
                my_wallets = user_wallets[chat_id]
                if my_wallets:
                    wallet_list = "\n".join([f"• `{w[:6]}...{w[-4:]}`" for w in my_wallets.keys()])
                    send_telegram_alert(chat_id, f"📋 *Your Tracked Wallets ({len(my_wallets)}):*\n\n{wallet_list}")
                else:
                    send_telegram_alert(chat_id, "📋 *You have no wallets currently tracked.*\nUse `/add <address>` to add one.")

            elif text == "/stats":
                raydium_count = stats["dex_breakdown"].get("Raydium ⚡", 0)
                pump_count = stats["dex_breakdown"].get("Pump.fun 💊", 0)
                unknown_count = stats["dex_breakdown"].get("Unknown DEX", 0)
                
                stats_msg = (
                    f"📊 *SOLANA TRACKER GLOBAL STATS*\n\n"
                    f"• *Total Trades Captured*: `{stats['total_trades']}`\n"
                    f"• *Total Buys*: `{stats['total_buys']} 🟢`\n"
                    f"• *Total Sells*: `{stats['total_sells']} 🔴`\n"
                    f"• *Total SOL Volume*: `{round(stats['total_sol_volume'], 2)} SOL`\n\n"
                    f"*DEX Distribution*:\n"
                    f"  - Raydium: `{raydium_count}`\n"
                    f"  - Pump.fun: `{pump_count}`\n"
                    f"  - Other/Unknown: `{unknown_count}`"
                )
                send_telegram_alert(chat_id, stats_msg)
                    
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Network retry on command check: {e}")

def check_wallet_activity():
    global stats, user_wallets
    headers = {"Content-Type": "application/json"}
    
    # Flatten unique wallets and map which chat_ids track them
    wallet_to_chats = {}
    for chat_id, wallets_dict in user_wallets.items():
        if isinstance(wallets_dict, dict):
            for wallet in wallets_dict.keys():
                if wallet not in wallet_to_chats:
                    wallet_to_chats[wallet] = []
                wallet_to_chats[wallet].append(chat_id)
            
    if not wallet_to_chats:
        return

    for wallet, chat_ids in wallet_to_chats.items():
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getSignaturesForAddress",
            "params": [wallet, {"limit": 5}]
        }
        try:
            res = requests.post(SOLANA_RPC, json=payload, headers=headers, timeout=15)
            res.raise_for_status()
            signatures = res.json().get("result", [])
            if not signatures:
                continue
                
            # Sort signatures from oldest to newest
            signatures = list(reversed(signatures))
            
            for chat_id in chat_ids:
                last_seen_sig = user_wallets.get(chat_id, {}).get(wallet)
                new_signatures_to_process = []
                found_marker = (last_seen_sig is None)
                
                for tx in signatures:
                    sig = tx.get("signature")
                    if not found_marker:
                        if sig == last_seen_sig:
                            found_marker = True
                        continue
                    else:
                        # If we passed the marker (or there was no prior marker), this is a new tx
                        if sig != last_seen_sig:
                            new_signatures_to_process.append(tx)
                
                # Update user's last seen signature to the absolute newest one available
                newest_sig = signatures[-1].get("signature")
                if newest_sig and chat_id in user_wallets and wallet in user_wallets[chat_id]:
                    user_wallets[chat_id][wallet] = newest_sig
                    save_wallets()

                for tx in new_signatures_to_process:
                    sig = tx.get("signature")
                    status = "❌ Failed" if tx.get("err") else "✅ Success"
                    slot = tx.get("slot")
                    
                    details = parse_transaction_details(sig)
                    
                    if details:
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
                        
                    send_telegram_alert(chat_id, msg)
                    
        except Exception as e:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Solana RPC retry for {wallet[:6]}: {e}")

if __name__ == "__main__":
    print("Starting Multi-User Solana Tracker with Persistent State Sync...")
    while True:
        try:
            handle_commands()
            check_wallet_activity()
        except Exception as main_e:
            print(f"Main loop recovered from error: {main_e}")
        time.sleep(5)
