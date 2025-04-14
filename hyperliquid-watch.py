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
        parts = relative_str.split()
        value = int(parts[0])
        unit = parts[1].lower().rstrip('s')  # Handle "minutes" vs "minute"
        
        if 'minute' in unit:
            delta = timedelta(minutes=value)
        elif 'hour' in unit:
            delta = timedelta(hours=value)
        else:
            return None
            
        return current_utc - delta
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
        # Load page with extended timeout
        page.goto(f'https://hypurrscan.io/address/{WALLET_ADDRESS}', timeout=120000)
        
        # Wait for data table - more specific selector
        page.wait_for_selector('div.v-data-table table tbody tr:not(.v-data-table-header)', timeout=60000)
        page.wait_for_timeout(5000)  # Extra stabilization
        
        current_utc = datetime.now(pytz.UTC)
        time_threshold = current_utc - timedelta(minutes=8)  # 8-minute window
        
        # Find ALL transaction rows
        transactions = page.query_selector_all('div.v-data-table table tbody tr')
        new_trades = []
        
        for tx in transactions:
            cells = tx.query_selector_all('td')
            if len(cells) >= 7:
                # Get transaction details
                relative_time = cells[2].inner_text().strip()
                tx_time = parse_relative_time(relative_time, current_utc)
                tx_type = cells[1].inner_text().strip()  # "Open Long" or "Close Short"
                
                # Check if within time window and has valid type
                if tx_time and tx_time >= time_threshold:
                    if "Open" in tx_type or "Close" in tx_type:  # Changed to substring check
                        asset = cells[5].inner_text().strip()
                        size = cells[4].inner_text().strip()
                        price = cells[6].inner_text().strip()
                        new_trades.append(
                            f"{tx_time.strftime('%H:%M:%S UTC')} - {tx_type} {size} {asset} @ {price}"
                        )

        if new_trades:
            message = "🔥 New Trades:\n" + "\n".join(new_trades[:5])
            print(f"Sending alert: {message}")
            send_telegram_alert(message)
        else:
            print("No new trades detected")
            
    except Exception as e:
        error_msg = f"🚨 Error: {str(e)}"
        print(error_msg)
        send_telegram_alert(error_msg)
    finally:
        browser.close()
