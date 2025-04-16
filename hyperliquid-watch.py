import os
import requests
from playwright.sync_api import sync_playwright
from datetime import datetime, timedelta
import pytz
import re

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
WALLET_ADDRESS = '0xf6B48AA4FD6786e0E4f94B009eA77702F2A36c60'
TIME_WINDOW_MINUTES = 3  # Reduced to 3 minutes for GitHub Actions timing

def send_telegram_alert(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        data = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
        response = requests.post(url, data=data, timeout=10)
        response.raise_for_status()
    except Exception as e:
        print(f"Telegram API Error: {str(e)}")

def parse_relative_time(relative_str):
    try:
        match = re.match(r'(\d+)\s+(min|mins|hour|hours)\s+ago', relative_str)
        if not match:
            return None
            
        value = int(match.group(1))
        unit = match.group(2).rstrip('s')

        if unit == 'min':
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
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        viewport={"width": 1920, "height": 1080},
        timezone_id="UTC"
    )
    page = context.new_page()
    
    try:
        page.goto(f'https://hypurrscan.io/address/{WALLET_ADDRESS}', timeout=120000)
        page.wait_for_selector('div.v-data-table table tbody tr:has(td:has-text("min"))', timeout=60000)

        current_utc = datetime.now(pytz.UTC)
        time_threshold = current_utc - timedelta(minutes=TIME_WINDOW_MINUTES)
        new_trades = []

        transactions = page.query_selector_all('div.v-data-table table tbody tr')
        print(f"Found {len(transactions)} transactions")

        for index, tx in enumerate(transactions, 1):
            cells = tx.query_selector_all('td')
            if len(cells) < 6:
                continue

            try:
                # Current Hypurrscan columns (2025-04-16):
                # 0: Expand | 1: Type | 2: Time | 3: Size | 4: Asset | 5: Price
                time_cell = cells[2].inner_text().strip()
                tx_time = parse_relative_time(time_cell)
                
                if not tx_time:
                    print(f"Skipped row {index}: Invalid time format - '{time_cell}'")
                    continue
                    
                if tx_time < time_threshold:
                    print(f"Skipped row {index}: Outside time window ({tx_time} < {time_threshold})")
                    continue

                tx_type = cells[1].inner_text().strip()
                size = cells[3].inner_text().strip()
                asset = cells[4].inner_text().strip()
                price = cells[5].inner_text().strip()

                new_trades.append(
                    f"{tx_time.strftime('%H:%M:%S UTC')} - {tx_type} {size} {asset} @ {price}"
                )
                print(f"New trade found: {tx_time} | {tx_type} | {size} {asset}")

            except Exception as e:
                print(f"Error processing row {index}: {str(e)}")
                continue

        if new_trades:
            message = "🚨 New Trade Alert:\n" + "\n".join(new_trades[:5])
            send_telegram_alert(message)
        else:
            print(f"No new trades in last {TIME_WINDOW_MINUTES} minutes (threshold: {time_threshold})")
            
    except Exception as e:
        error_msg = f"🚨 Critical Error: {str(e)}"
        print(error_msg)
        send_telegram_alert(error_msg)
    finally:
        browser.close()
