import requests
import json
import time
import os
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
SOLANA_RPC = "https://api.mainnet-beta.solana.com"
WALLETS_FILE = "wallets.json"
STATS_FILE = "stats.json"

BASE_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

# (Rest of your script remains identical)
