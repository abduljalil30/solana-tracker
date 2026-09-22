import requests
import json
import time
from datetime import datetime

# RPC Configuration
SOLANA_RPC = "https://api.mainnet-beta.solana.com"
TARGET_WALLET = "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8"

def fetch_latest_signatures(wallet_address, limit=3):
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getSignaturesForAddress",
        "params": [wallet_address, {"limit": limit}]
    }
    headers = {"Content-Type": "application/json"}
    
    try:
        res = requests.post(SOLANA_RPC, json=payload, headers=headers, timeout=10)
        res.raise_for_status()
        return res.json().get("result", [])
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] RPC Error: {e}")
        return []

def run_monitor():
    print(f"=== Solana Wallet Tracker Started ===")
    print(f"Target: {TARGET_WALLET[:8]}...{TARGET_WALLET[-4:]}")
    
    signatures = fetch_latest_signatures(TARGET_WALLET)
    if not signatures:
        print("No transactions fetched.")
        return

    print(f"\nFetched {len(signatures)} recent transactions:")
    for tx in signatures:
        sig = tx.get("signature")
        status = "FAILED" if tx.get("err") else "SUCCESS"
        print(f"• Sig: {sig[:16]}... | Status: {status} | Slot: {tx.get('slot')}")
        print(f"  View: https://solscan.io/tx/{sig}")

if __name__ == "__main__":
    run_monitor()
