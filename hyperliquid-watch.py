import requests
from playwright.sync_api import sync_playwright
from datetime import datetime, timedelta

TELEGRAM_BOT_TOKEN = 'YOUR_BOT_TOKEN'
TELEGRAM_CHAT_ID = 'YOUR_CHAT_ID'
WALLET_ADDRESS = '0xf6B48AA4FD6786e0E4f94B009eA77702F2A36c60'

def send_telegram_alert(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    requests.post(url, data=data)

def parse_transactions(content):
    # Look for these transaction types
    triggers = ["Open Long", "Open Short", "Close Long", "Close Short"]
    return [line for line in content.split('\n') if any(t in line for t in triggers)]

with sync_playwright() as p:
    browser = p.chromium.launch()
    context = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        viewport={"width": 1920, "height": 1080}
    )
    page = context.new_page()
    
    try:
        # Load transactions page
        page.goto(f'https://hypurrscan.io/address/{WALLET_ADDRESS}')
        
        # Wait for transaction table or no-data message
        page.wait_for_selector('.v-data-table, div.text-center:has-text("No data available")', timeout=60000)
        
        # Handle pagination if needed
        page.select_option('div.items-per-page-select select', value='100')
        page.wait_for_timeout(3000)  # Wait for page reload
        
        # Get current time to detect new transactions
        current_time = datetime.utcnow()
        time_threshold = current_time - timedelta(minutes=15)
        
        # Extract transaction rows
        transactions = page.query_selector_all('tr[role="row"]')
        new_trades = []
        
        for tx in transactions:
            cells = tx.query_selector_all('td')
            if len(cells) >= 7:
                timestamp_str = cells[2].inner_text().strip()
                tx_type = cells[1].inner_text().strip()
                asset = cells[5].inner_text().strip()
                
                try:
                    tx_time = datetime.strptime(timestamp_str, "%m/%d/%Y, %I:%M:%S %p")
                except:
                    continue
                
                if tx_time > time_threshold and any(t in tx_type for t in ["Open", "Close"]):
                    size = cells[4].inner_text().strip()
                    price = cells[6].inner_text().strip()
                    new_trades.append(f"{tx_time} - {tx_type} {size} {asset} @ {price}")

        # Send alerts if new trades found
        if new_trades:
            message = "🔥 New Hyperliquid Trades:\n" + "\n".join(new_trades[:5])  # Send max 5 trades
            send_telegram_alert(message)
        else:
            print("No new trades in the last 15 minutes")
            
    except Exception as e:
        print(f"Error: {str(e)}")
        send_telegram_alert(f"🚨 Script Error: {str(e)}")
        
    finally:
        browser.close()
