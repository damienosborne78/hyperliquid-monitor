import os
import requests
from playwright.sync_api import sync_playwright
from datetime import datetime, timedelta
import pytz
import re

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
WALLET_ADDRESS = '0x73216e4edb979ffa84cc8bf55374a161e7d08ad5'

def send_telegram_alert(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    response = requests.post(url, data=data)
    print(f"Telegram API Response: {response.status_code}")

def parse_relative_time(relative_str):
    try:
        # Match patterns like "5 minutes ago" or "30 seconds ago"
        match = re.match(r'(\d+)\s+(second|minute|hour)s?\s+ago', relative_str)
        if not match:
            return None
            
        value = int(match.group(1))
        unit = match.group(2)
        
        if unit.startswith('second'):
            delta = timedelta(seconds=value)
        elif unit.startswith('minute'):
            delta = timedelta(minutes=value)
        elif unit.startswith('hour'):
            delta = timedelta(hours=value)
        else:
            return None
            
        return datetime.now(pytz.UTC) - delta
    except Exception as e:
        print(f"Time parse error: {str(e)}")
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
        # Load page with retries and proper waiting
        page.goto(f'https://hypurrscan.io/address/{WALLET_ADDRESS}', timeout=120000)
        page.wait_for_selector('div.v-data-table table tbody tr:has(td:has-text("ago"))', timeout=60000)
        
        current_time = datetime.now(pytz.UTC)
        time_threshold = current_time - timedelta(minutes=5)
        
        transactions = page.query_selector_all('div.v-data-table table tbody tr')
        new_trades = []
        
        print(f"Found {len(transactions)} transactions")
        
        for tx in transactions:
            cells = tx.query_selector_all('td')
            if len(cells) < 7:
                continue
                
            try:
                # Extract and validate time
                time_cell = cells[2].inner_text().strip()  # Adjusted column index
                tx_time = parse_relative_time(time_cell)
                
                if not tx_time or tx_time < time_threshold:
                    continue
                
                # Extract other fields
                tx_type = cells[1].inner_text().strip()
                size = cells[3].inner_text().strip()
                asset = cells[4].inner_text().strip()
                price = cells[5].inner_text().strip()
                
                if "Open" in tx_type or "Close" in tx_type:
                    new_trades.append(
                        f"{tx_time.strftime('%H:%M:%S UTC')} - {tx_type} {size} {asset} @ {price}"
                    )
                    
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
