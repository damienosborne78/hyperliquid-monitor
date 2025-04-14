import os
from playwright.sync_api import sync_playwright
import requests

# Telegram config
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
WALLET_ADDRESS = "0xf6B48AA4FD6786e0E4f94B009eA77702F2A36c60"

def send_telegram_alert(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    params = {'chat_id': TELEGRAM_CHAT_ID, 'text': message}
    requests.post(url, params=params)

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    
    # Load the Hyperliquid wallet page
    page.goto(f'https://hypurrscan.io/address/{WALLET_ADDRESS}')
    
    # Wait for transactions to load (adjust selector if needed)
    page.wait_for_selector('.v-table tbody tr', timeout=30000)
    
    # Check for new "Open Short" transactions
    content = page.inner_text('.v-table')
    if "Open Short" in content:
        send_telegram_alert(f"New Hyperliquid trade detected!\n{content[:500]}...")
    
    browser.close()
