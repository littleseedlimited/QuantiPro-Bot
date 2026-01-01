from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, filters
from src.database.db_manager import DatabaseManager
from src.utils.logger import logger

from src.bot.constants import (
    S_NAME, S_EMAIL, S_PHONE, S_COUNTRY
)

class SignupManager:
    """
    Handles the user registration process.
    """
    
    @staticmethod
    async def start_signup(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "📝 **Registration Required**\n\n"
            "To use QuantiProBot, please complete a quick signup.\n"
            "First, what is your **Full Name**?",
            parse_mode='Markdown',
            reply_markup=ReplyKeyboardRemove()
        )
        return S_NAME

    @staticmethod
    async def handle_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
        context.user_data['reg_name'] = update.message.text
        await update.message.reply_text("Understood. Please provide your **Email Address**:")
        return S_EMAIL

    @staticmethod
    async def handle_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
        context.user_data['reg_email'] = update.message.text
        # Optional: Basic email validation logic here
        await update.message.reply_text("Thank you. What is your **Phone Number**?")
        return S_PHONE

    @staticmethod
    async def handle_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
        context.user_data['reg_phone'] = update.message.text
        await update.message.reply_text("Finally, which **Country** are you in?")
        return S_COUNTRY

    @staticmethod
    async def handle_country(update: Update, context: ContextTypes.DEFAULT_TYPE):
        country = update.message.text.strip()
        user_id = update.message.from_user.id
        
        if not country or len(country) < 2:
            await update.message.reply_text("Please provide a valid country name:")
            return S_COUNTRY

        db = DatabaseManager()
        
        # Expanded Currency Mapping
        currency_map = {
            "Nigeria": "NGN",
            "Ghana": "GHS",
            "Kenya": "KES",
            "South Africa": "ZAR",
            "United Kingdom": "GBP",
            "UK": "GBP",
            "USA": "USD",
            "United States": "USD",
            "Canada": "CAD",
            "European Union": "EUR",
            "Germany": "EUR",
            "France": "EUR",
            "Italy": "EUR",
            "Spain": "EUR"
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
            await update.message.reply_text("❌ There was an error during registration. Please try again with /start.")
            return ConversationHandler.END
