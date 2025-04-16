import os
import requests
from playwright.sync_api import sync_playwright
from datetime import datetime, timedelta
import pytz

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
WALLET_ADDRESS = '0xf6B48AA4FD6786e0E4f94B009eA77702F2A36c60'

def send_telegram_alert(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    response = requests.post(url, data=data)
    print(f"Telegram API Response: {response.status_code}")

def parse_relative_time(relative_str, current_utc):
    try:
        # Filter out transaction hashes and invalid formats
        if not relative_str.endswith(' ago') or '...' in relative_str:
            return None
            
        clean_str = relative_str.replace(' ago', '').strip()
        parts = clean_str.split()
        
        if len(parts) != 2:
            return None
            
        value = int(parts[0])
        unit = parts[1].lower().rstrip('s')
        
        if 'second' in unit:
            delta = timedelta(seconds=value)
        elif 'minute' in unit:
            delta = timedelta(minutes=value)
        elif 'hour' in unit:
            delta = timedelta(hours=value)
        else:
            return None
            
        return current_utc - delta
    except Exception as e:
        print(f"Skipping invalid time format: '{relative_str}' - {str(e)}")
        return None

with sync_playwright() as p:
    browser = p.chromium.launch()
    context = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        viewport={"width": 1920, "height": 1080},
        timezone_id="UTC"
    )
    page = context.new_page()
    
    try:
        page.goto(f'https://hypurrscan.io/address/{WALLET_ADDRESS}', timeout=120000)
        
        # Wait for both table and specific time elements
        page.wait_for_selector('div.v-data-table table tbody tr td:nth-child(1):has-text("ago")', timeout=60000)
        page.wait_for_timeout(2000)
        
        current_utc = datetime.now(pytz.UTC)
        time_threshold = current_utc - timedelta(minutes=4, seconds=45)  # 4m45s buffer
        
        transactions = page.query_selector_all('div.v-data-table table tbody tr')
        new_trades = []
        
        print(f"Processing {len(transactions)} transactions...")
        
        for tx in transactions:
            cells = tx.query_selector_all('td')
            if len(cells) >= 6:
                try:
                    # Current Hypurrscan columns (verified 2025-04-16):
                    # 0: Time | 1: Type | 2: Size | 3: Asset | 4: Price
                    time_cell = cells[0].inner_text().strip()
                    tx_time = parse_relative_time(time_cell, current_utc)
                    
                    if not tx_time or tx_time < time_threshold:
                        continue
                        
                    tx_type = cells[1].inner_text().strip()
                    size = cells[2].inner_text().strip()
                    asset = cells[3].inner_text().strip()
                    price = cells[4].inner_text().strip()

                    if "Open" in tx_type or "Close" in tx_type:
                        new_trades.append(
                            f"{tx_time.strftime('%H:%M:%S UTC')} - {tx_type} {size} {asset} @ {price}"
                        )
                        print(f"New trade found: {tx_type} {asset}")
                        
                except Exception as e:
                    print(f"Skipping invalid row: {str(e)}")
                    continue

        if new_trades:
            message = "🚨 New Trade Alert:\n" + "\n".join(new_trades[:5])
            send_telegram_alert(message)
        else:
            print(f"No new trades in last 5 minutes (threshold: {time_threshold})")
            
    except Exception as e:
        error_msg = f"🚨 Critical Error: {str(e)}"
        print(error_msg)
        send_telegram_alert(error_msg)
    finally:
        browser.close()
