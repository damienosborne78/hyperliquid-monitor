import os
import requests
from playwright.sync_api import sync_playwright
from datetime import datetime, timedelta
import pytz
import re

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
WALLET_ADDRESS = '0xf6B48AA4FD6786e0E4f94B009eA77702F2A36c60'

def send_telegram_alert(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    requests.post(url, data=data)

def parse_relative_time(relative_str):
    try:
        match = re.match(r'(\d+)\s+(minute|hour)s?\s+ago', relative_str, re.IGNORECASE)
        if not match:
            return None
            
        value = int(match.group(1))
        unit = match.group(2).lower()

        if unit == 'minute':
            delta = timedelta(minutes=value)
        elif unit == 'hour':
            delta = timedelta(hours=value)
        else:
            return None
            
        return datetime.now(pytz.UTC) - delta
    except Exception as e:
        print(f"Time parse error: {str(e)}")
        return None

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    
    try:
        # Load page and wait for network requests
        page.goto(f'https://hypurrscan.io/address/{WALLET_ADDRESS}', wait_until='networkidle')
        
        # Wait for dynamic content
        page.wait_for_selector('div.v-data-table table tbody tr', timeout=15000)
        
        current_utc = datetime.now(pytz.UTC)
        time_threshold = current_utc - timedelta(minutes=5)
        new_trades = []
        
        # Get all transaction rows
        transactions = page.query_selector_all('div.v-data-table table tbody tr')
        print(f"Found {len(transactions)} transactions")

        for tx in transactions:
            cells = tx.query_selector_all('td')
            if len(cells) >= 6:
                try:
                    # Current column structure:
                    # 0: Expand | 1: Type | 2: Time | 3: Size | 4: Asset | 5: Price
                    time_cell = cells[2].inner_text().strip()
                    tx_time = parse_relative_time(time_cell)
                    
                    if tx_time and tx_time >= time_threshold:
                        tx_type = cells[1].inner_text().strip()
                        size = cells[3].inner_text().strip()
                        asset = cells[4].inner_text().strip()
                        price = cells[5].inner_text().strip()

                        new_trades.append(
                            f"{tx_time.strftime('%H:%M:%S UTC')} - {tx_type} {size} {asset} @ {price}"
                        )
                except Exception as e:
                    print(f"Error processing row: {str(e)}")

        if new_trades:
            message = "🚨 New Trade Alert:\n" + "\n".join(new_trades)
            send_telegram_alert(message)
        else:
            print(f"No new trades in last 5 minutes (threshold: {time_threshold})")
            
    except Exception as e:
        print(f"Error: {str(e)}")
    finally:
        browser.close()
