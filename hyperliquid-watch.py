import requests
from playwright.sync_api import sync_playwright

TELEGRAM_BOT_TOKEN = 'YOUR_BOT_TOKEN'
TELEGRAM_CHAT_ID = 'YOUR_CHAT_ID'
WALLET_ADDRESS = '0xf6B48AA4FD6786e0E4f94B009eA77702F2A36c60'

def send_telegram_alert(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    requests.post(url, data=data)

with sync_playwright() as p:
    browser = p.chromium.launch()
    context = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
    )
    page = context.new_page()
    
    try:
        page.goto(f'https://hypurrscan.io/address/{WALLET_ADDRESS}')
        
        # Wait for either data or "No data" message
        page.wait_for_selector('.v-data-table, div.text-center:has-text("No data available")', timeout=60000)
        
        # Force wait for dynamic content
        page.wait_for_timeout(5000)  # Additional 5 seconds
        
        content = page.inner_text('body')
        
        print("=== FULL PAGE CONTENT ===")
        print(content[:2000])  # First 2000 chars
        print("========================")
        
        if "Open Short" in content or "Open Long" in content:
            send_telegram_alert(f"New trade detected!\n{content[:500]}...")
        else:
            print("No trades found in content")
            
    except Exception as e:
        print(f"Error: {str(e)}")
        send_telegram_alert(f"Script error: {str(e)}")
        
    finally:
        browser.close()
