
import os
import asyncio
from telegram import Bot
from dotenv import load_dotenv

async def check():
    load_dotenv()
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        print("No token found")
        return
    
    bot = Bot(token)
    try:
        me = await bot.get_me()
        print(f"Bot Username: @{me.username}")
        print(f"Bot Name: {me.first_name}")
        
        webhook = await bot.get_webhook_info()
        print(f"Webhook URL: {webhook.url if webhook.url else 'None (Polling mode)'}")
        if webhook.url:
            print("WARNING: Webhook is set! getUpdates will not work until it is deleted.")
            # await bot.delete_webhook()
            # print("Webhook deleted.")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(check())
