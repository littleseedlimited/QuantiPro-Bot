
import os
import asyncio
from telegram import Bot
from dotenv import load_dotenv

async def test_send():
    load_dotenv()
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    user_id = 1241907317
    
    bot = Bot(token)
    try:
        msg = await bot.send_message(chat_id=user_id, text="🔔 **Connectivity Test**\n\nIf you see this, the bot backend is online and can reach you. Please try pressing '📉 Describe & Explore' again.", parse_mode='Markdown')
        print(f"Message sent successfully! ID: {msg.message_id}")
    except Exception as e:
        print(f"Failed to send message: {e}")

if __name__ == "__main__":
    asyncio.run(test_send())
