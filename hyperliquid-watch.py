import os
import requests
from playwright.sync_api import sync_playwright
from datetime import datetime, timedelta

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
WALLET_ADDRESS = '0xf6B48AA4FD6786e0E4f94B009eA77702F2A36c60'

def send_telegram_alert(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    response = requests.post(url, data=data)
    print(f"Telegram API Response: {response.status_code}")

def parse_timestamp(timestamp_str):
    try:
        return datetime.strptime(timestamp_str, "%m/%d/%Y, %I:%M:%S %p")
    except ValueError:
        return None

with sync_playwright() as p:
    browser = p.chromium.launch()
    context = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        viewport={"width": 1920, "height": 1080}
    )
    page = context.new_page()
    
    try:
        # Load page with extended timeout
        page.goto(f'https://hypurrscan.io/address/{WALLET_ADDRESS}', timeout=120000)
        
        # Wait for EITHER transactions OR no-data message
        try:
            page.wait_for_selector('.v-data-table:has(tr)', timeout=60000)
        except:
            page.wait_for_selector('div.text-center:has-text("No data available")', timeout=10000)
        
        # Additional stabilization wait
        page.wait_for_timeout(3000)
        
        # Check for no-data scenario first
        if page.query_selector('div.text-center:has-text("No data available")'):
            print("No transactions found in wallet")
            browser.close()
            exit(0)
            
        transactions = page.query_selector_all('.v-data-table tr:not(.v-data-table-header)')
        current_time = datetime.utcnow()
        time_threshold = current_time - timedelta(minutes=15)
        new_trades = []
        
        for tx in transactions:
            cells = tx.query_selector_all('td')
            if len(cells) >= 7:
                timestamp = parse_timestamp(cells[2].inner_text().strip())
                tx_type = cells[1].inner_text().strip()
                
                if timestamp and timestamp > time_threshold:
                    asset = cells[5].inner_text().strip()
                    size = cells[4].inner_text().strip()
                    price = cells[6].inner_text().strip()
                    
                    if any(t in tx_type for t in ["Open", "Close"]):
                        new_trades.append(
                            f"{timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')} - "
                            f"{tx_type} {size} {asset} @ {price}"
                        )

        if new_trades:
            message = "🔥 New Hyperliquid Trades:\n" + "\n".join(new_trades[:5])
            print(f"Sending alert:\n{message}")
            send_telegram_alert(message)
        else:
            print("No new trades detected in the last 15 minutes")
            
    except Exception as e:
        error_msg = f"🚨 Critical Error: {str(e)}\nPage Content:\n{page.content()[:1000]}..."
        print(error_msg)
        send_telegram_alert(error_msg)
        
    finally:
        browser.close()
