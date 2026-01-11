from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, filters
from src.database.db_manager import DatabaseManager
from src.utils.logger import logger

from src.bot.constants import (
    S_ID, S_NAME, S_EMAIL, S_PHONE, S_COUNTRY, S_USERNAME, S_VERIFY_CODE
)
import re
import random

class SignupManager:
    """
    Handles the user registration process.
    """
    
    @staticmethod
    async def start_signup(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "📝 **Verification Required**\n\n"
            "To use QuantiProBot, you must verify your identity.\n"
            "Please enter your **Telegram ID** (numeric).\n\n"
            "ℹ️ *How to find it?*\n"
            "1. Go to your Settings > Profile\n"
            "2. Or forward a message to @userinfobot",
            parse_mode='Markdown',
            reply_markup=ReplyKeyboardRemove()
        )
        return S_ID

    @staticmethod
    async def handle_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_input = update.message.text.strip()
        actual_id = update.effective_user.id
        
        if not user_input.isdigit():
             await update.message.reply_text("⚠️ Invalid ID. Please enter numeric digits only.")
             return S_ID

        if str(user_input) != str(actual_id):
            await update.message.reply_text(
                f"⚠️ The ID you entered ({user_input}) does not match your current account ID ({actual_id}).\n"
                "Please enter your **actual Telegram ID** to proceed.",
                parse_mode='Markdown'
            )
            return S_ID

        # Generate 4-digit verification code
        verify_code = str(random.randint(1000, 9999))
        context.user_data['reg_id'] = user_input
        context.user_data['verify_code'] = verify_code
        
        # Send code to user
        await update.message.reply_text(
            f"🔐 **Verification Code Sent!**\n\n"
            f"I have sent a 4-digit code to your Telegram ID ({user_input}).\n"
            f"**Please enter the code here to verify your account:**\n\n"
            f"_(Debug: Use {verify_code} for now)_",
            parse_mode='Markdown'
        )
        return S_VERIFY_CODE

    @staticmethod
    async def handle_verify_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_code = update.message.text.strip()
        actual_code = context.user_data.get('verify_code')
        
        if user_code != actual_code:
            await update.message.reply_text("❌ Incorrect verification code. Please try again:")
            return S_VERIFY_CODE
            
        await update.message.reply_text(
            "✅ **ID Verified!**\n\n"
            "Now, please enter your **Telegram Username** (including the @ symbol):\n"
            "_(e.g., @john_doe)_"
        )
        return S_USERNAME
        
    @staticmethod
    async def handle_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
        username = update.message.text.strip()
        if not username.startswith('@') or len(username) < 3:
            await update.message.reply_text("⚠️ A valid Telegram Username is **required** and must start with '@' (e.g., @john_doe).\n\nPlease enter your username to proceed:")
            return S_USERNAME
            
        context.user_data['reg_username'] = username
        await update.message.reply_text("Got it. Now, what is your **Full Name**?")
        return S_NAME

    @staticmethod
    async def handle_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
        context.user_data['reg_name'] = update.message.text
        await update.message.reply_text("Understood. Please provide your **Email Address**:")
        return S_EMAIL

    @staticmethod
    async def handle_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
        email = update.message.text.strip()
        EMAIL_REGEX = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
        
        if not re.match(EMAIL_REGEX, email):
            await update.message.reply_text("⚠️ Invalid email format. Please enter a valid email address (e.g., name@example.com):")
            return S_EMAIL

        context.user_data['reg_email'] = email
        await update.message.reply_text("Thank you. What is your **Phone Number** (including country code)?\n_(e.g., +2348012345678)_")
        return S_PHONE

    @staticmethod
    async def handle_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
        phone = update.message.text.strip()
        # Basic international phone regex: + followed by 7-15 digits
        PHONE_REGEX = r'^\+[1-9]\d{1,14}$'
        
        if not re.match(PHONE_REGEX, phone):
            await update.message.reply_text("⚠️ Invalid phone format. Please use international format starting with + (e.g., +2348012345678):")
            return S_PHONE
            
        context.user_data['reg_phone'] = phone
        await update.message.reply_text("Finally, which **Country** are you in?")
        return S_COUNTRY

    @staticmethod
    async def handle_country(update: Update, context: ContextTypes.DEFAULT_TYPE):
        country = update.message.text.strip()
        user_id = update.message.from_user.id
        
        # List of supported/valid countries (can be expanded)
        VALID_COUNTRIES = [
            "Nigeria", "Ghana", "Kenya", "South Africa", "United Kingdom", "UK", 
            "USA", "United States", "Canada", "Germany", "France", "Italy", "Spain",
            "China", "India", "Australia", "Brazil", "Egypt", "Ethiopia", "Uganda"
        ]
        
        is_valid = any(c.lower() in country.lower() for c in VALID_COUNTRIES)
        if not is_valid and len(country) < 3:
             await update.message.reply_text("⚠️ Please provide a clear country name (e.g., Nigeria, USA):")
             return S_COUNTRY

        db = DatabaseManager()
        
        # Expanded Currency Mapping
        currency_map = {
            "Nigeria": "NGN", "Ghana": "GHS", "Kenya": "KES", "South Africa": "ZAR",
            "United Kingdom": "GBP", "UK": "GBP", "USA": "USD", "United States": "USD",
            "Canada": "CAD", "Germany": "EUR", "France": "EUR", "Italy": "EUR", "Spain": "EUR"
        }
        
        # Try to find a match, default to USD if not found but still allow signup
        currency = "USD"
        for k, v in currency_map.items():
            if k.lower() in country.lower():
                currency = v
                break
        
        try:
            db.create_user(
                telegram_id=user_id,
                full_name=context.user_data['reg_name'],
                username=context.user_data['reg_username'],
                email=context.user_data['reg_email'],
                phone=context.user_data['reg_phone'],
                country=country,
                local_currency=currency
            )
            
            await update.message.reply_text(
                f"✅ **Registration Complete!**\n\n"
                f"Welcome, {context.user_data['reg_name']}. You are on the **Free Plan**.\n"
                f"Local Pricing set to: **{currency}**\n\n"
                f"Use /help to see what I can do or send /start to begin your analysis.",
                parse_mode='Markdown'
            )
            return ConversationHandler.END
            
        except Exception as e:
            logger.error(f"Signup failed for {user_id}: {e}")
            await update.message.reply_text(f"❌ Registration Error: {str(e)}\n\nPlease try again with /start or contact support.")
            return ConversationHandler.END
