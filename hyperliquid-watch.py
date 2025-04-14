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
    """Convert 'X minutes ago' format to UTC datetime"""
    try:
        parts = relative_str.split()
        if len(parts) < 2:
            return None
            
        value = int(parts[0])
        unit = parts[1].lower().rstrip('s')  # Normalize units
        
        if 'minute' in unit:
            delta = timedelta(minutes=value)
        elif 'hour' in unit:
            delta = timedelta(hours=value)
        else:
            print(f"Unhandled time unit: {unit}")
            return None
            
        return current_utc - delta
    except Exception as e:
        print(f"Time parse error: {relative_str} - {str(e)}")
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
        # Load page
        page.goto(f'https://hypurrscan.io/address/{WALLET_ADDRESS}', timeout=120000)
        print("Page loaded successfully")
        
        # Wait for transactions
        page.wait_for_selector('div.v-data-table table tbody tr', timeout=60000)
        page.wait_for_timeout(3000)  # Stabilization
        
        # Time setup
        current_utc = datetime.now(pytz.UTC)
        time_threshold = current_utc - timedelta(minutes=5)  # 5-min window for cron
        
        print(f"Current UTC: {current_utc.isoformat()}")
        print(f"Threshold: {time_threshold.isoformat()}")
        
        # Process transactions
        transactions = page.query_selector_all('div.v-data-table table tbody tr')
        new_trades = []
        
        for tx in transactions:
            cells = tx.query_selector_all('td')
            if len(cells) >= 7:
                relative_time = cells[2].inner_text().strip()
                tx_time = parse_relative_time(relative_time, current_utc)
                
                print(f"Raw: {relative_time} → Parsed: {tx_time}")
                
                if tx_time and tx_time > time_threshold:
                    tx_type = cells[1].inner_text().strip()
                    asset = cells[5].inner_text().strip()
                    size = cells[4].inner_text().strip()
                    price = cells[6].inner_text().strip()
                    
                    new_trades.append(
                        f"{tx_time.strftime('%Y-%m-%d %H:%M:%S UTC')} - "
                        f"{tx_type} {size} {asset} @ {price}"
                    )

        # Send alerts
        if new_trades:
            message = "🔥 New Trades:\n" + "\n".join(new_trades[:5])
            print(f"Sending alert:\n{message}")
            send_telegram_alert(message)
        else:
            print("No new trades detected")
            
    except Exception as e:
        error_msg = f"🚨 Error: {str(e)}"
        print(error_msg)
        send_telegram_alert(error_msg)
        
    finally:
        browser.close()
