# 🚀 Multi-User Solana DEX Tracker Bot

A secure, multi-user Telegram bot built in Python (optimized for Termux/Android) that tracks Solana wallet activity in real time for decentralized exchanges like **Raydium** and **Pump.fun**.

## ✨ Features
* **Multi-User Isolation:** Each Telegram chat manages its own private roster of tracked wallets.
* **Silent Historical Pre-Sync:** Automatically bookmarks wallet states upon addition to prevent spam from historical transactions.
* **DEX Intelligence:** Parses transaction payloads to detect `BUY 🟢`, `SELL 🔴`, and `SWAP 🔄` actions, calculating SOL amounts and token mints.
* **Security First:** Credential isolation via `.env` configuration to protect your Telegram bot token.

## 📱 Telegram Commands
* `/add <address>` - Add a Solana wallet to your personal tracking list (silently syncs history).
* `/remove <address>` - Remove a wallet from your tracking list.
* `/list` - View all wallets currently tracked by you.
* `/stats` - View global bot trading statistics and DEX volume breakdown.
