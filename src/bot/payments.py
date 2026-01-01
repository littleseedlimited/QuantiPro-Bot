"""
Payment Integration Module for QuantiProBot
Supports: Paystack (Africa) and Telegram Stars
"""

import os
import httpx
import hashlib
import hmac
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from telegram import Update, LabeledPrice
from telegram.ext import ContextTypes

PAYSTACK_SECRET_KEY = os.getenv("PAYSTACK_SECRET_KEY", "")
PAYSTACK_PUBLIC_KEY = os.getenv("PAYSTACK_PUBLIC_KEY", "")


class PaymentManager:
    """Handles all payment operations for Paystack and Telegram Stars."""
    
    # Plan prices in USD
    PLANS = {
        "Student": {"monthly": 9.99, "yearly": 89.99, "stars": 500},
        "Researcher": {"monthly": 24.99, "yearly": 224.99, "stars": 1250},
        "Institution": {"monthly": 99.99, "yearly": 899.99, "stars": 5000},
    }
    
    # Currency conversion rates (approximate)
    RATES = {
        "NGN": 1600,  # Nigerian Naira
        "GHS": 15,     # Ghanaian Cedi
        "KES": 155,    # Kenyan Shilling
        "ZAR": 19,     # South African Rand
        "USD": 1,
        "GBP": 0.79,
        "EUR": 0.92,
    }
    
    @classmethod
    def get_price_in_currency(cls, plan: str, period: str, currency: str) -> float:
        """Convert USD price to local currency."""
        if plan not in cls.PLANS:
            return 0
        
        usd_price = cls.PLANS[plan].get(period, cls.PLANS[plan]["monthly"])
        rate = cls.RATES.get(currency, 1)
        return round(usd_price * rate, 2)
    
    @classmethod
    def get_stars_price(cls, plan: str) -> int:
        """Get Telegram Stars price for a plan."""
        return cls.PLANS.get(plan, {}).get("stars", 0)


class PaystackPayment:
    """Paystack integration for African payments."""
    
    BASE_URL = "https://api.paystack.co"
    
    def __init__(self):
        self.secret_key = PAYSTACK_SECRET_KEY
        self.headers = {
            "Authorization": f"Bearer {self.secret_key}",
            "Content-Type": "application/json"
        }
    
    async def initialize_transaction(
        self,
        email: str,
        amount: int,  # Amount in kobo (NGN) or pesewas (GHS)
        currency: str = "NGN",
        plan_name: str = "Student",
        user_id: int = 0,
        period: str = "monthly"
    ) -> Dict[str, Any]:
        """Initialize a Paystack transaction."""
        
        reference = f"QP_{user_id}_{plan_name}_{period}_{int(datetime.now().timestamp())}"
        
        payload = {
            "email": email,
            "amount": amount,  # In smallest currency unit
            "currency": currency,
            "reference": reference,
            "callback_url": os.getenv("PAYSTACK_CALLBACK_URL", "https://quantiprobot.com/payment/callback"),
            "metadata": {
                "user_id": user_id,
                "plan": plan_name,
                "period": period,
                "custom_fields": [
                    {"display_name": "Plan", "variable_name": "plan", "value": plan_name},
                    {"display_name": "Period", "variable_name": "period", "value": period}
                ]
            }
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.BASE_URL}/transaction/initialize",
                    json=payload,
                    headers=self.headers,
                    timeout=30.0
                )
                data = response.json()
                
                if data.get("status"):
                    return {
                        "success": True,
                        "authorization_url": data["data"]["authorization_url"],
                        "reference": data["data"]["reference"],
                        "access_code": data["data"]["access_code"]
                    }
                else:
                    return {"success": False, "error": data.get("message", "Unknown error")}
                    
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def verify_transaction(self, reference: str) -> Dict[str, Any]:
        """Verify a Paystack transaction."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.BASE_URL}/transaction/verify/{reference}",
                    headers=self.headers,
                    timeout=30.0
                )
                data = response.json()
                
                if data.get("status") and data["data"]["status"] == "success":
                    return {
                        "success": True,
                        "amount": data["data"]["amount"],
                        "currency": data["data"]["currency"],
                        "metadata": data["data"].get("metadata", {}),
                        "paid_at": data["data"]["paid_at"]
                    }
                else:
                    return {"success": False, "error": "Payment not successful"}
                    
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    @staticmethod
    def verify_webhook(payload: bytes, signature: str) -> bool:
        """Verify Paystack webhook signature."""
        computed = hmac.new(
            PAYSTACK_SECRET_KEY.encode(),
            payload,
            hashlib.sha512
        ).hexdigest()
        return computed == signature


class TelegramStarsPayment:
    """Telegram Stars payment integration."""
    
    @staticmethod
    async def send_invoice(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        plan_name: str,
        period: str = "monthly"
    ) -> bool:
        """Send a Telegram Stars invoice to the user."""
        
        stars = PaymentManager.get_stars_price(plan_name)
        if not stars:
            return False
        
        # Adjust for yearly (10 months price = ~17% discount)
        if period == "yearly":
            stars = int(stars * 10)  # 10 months for yearly
        
        title = f"QuantiProBot {plan_name} Plan"
        description = f"{plan_name} subscription ({period}). Includes: {PaymentManager.PLANS[plan_name].get('features', 'All features')}"
        
        # Payload for tracking
        payload = f"{plan_name}_{period}_{update.effective_user.id}"
        
        prices = [LabeledPrice(label=f"{plan_name} {period.title()}", amount=stars)]
        
        try:
            await context.bot.send_invoice(
                chat_id=update.effective_chat.id,
                title=title,
                description=description,
                payload=payload,
                provider_token="",  # Empty for Telegram Stars
                currency="XTR",  # Telegram Stars currency code
                prices=prices,
                start_parameter=f"subscribe_{plan_name.lower()}"
            )
            return True
        except Exception as e:
            print(f"Stars invoice error: {e}")
            return False
    
    @staticmethod
    async def handle_pre_checkout(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle pre-checkout query for Telegram Stars."""
        query = update.pre_checkout_query
        
        # Validate the payment
        if query.invoice_payload:
            await query.answer(ok=True)
        else:
            await query.answer(ok=False, error_message="Invalid payment")
    
    @staticmethod
    async def handle_successful_payment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Dict[str, Any]:
        """Handle successful Telegram Stars payment."""
        payment = update.message.successful_payment
        
        # Parse payload
        parts = payment.invoice_payload.split("_")
        if len(parts) >= 2:
            plan_name = parts[0]
            period = parts[1]
            user_id = int(parts[2]) if len(parts) > 2 else update.effective_user.id
            
            return {
                "success": True,
                "plan": plan_name,
                "period": period,
                "user_id": user_id,
                "stars_paid": payment.total_amount,
                "telegram_payment_id": payment.telegram_payment_charge_id
            }
        
        return {"success": False, "error": "Invalid payload"}


# Helper functions for handlers
async def initiate_paystack_payment(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    plan_name: str,
    period: str = "monthly"
) -> str:
    """Initiate Paystack payment and return payment URL."""
    from src.database.db_manager import DatabaseManager
    
    db = DatabaseManager()
    user = db.get_user(update.effective_user.id)
    
    if not user or not user.email:
        return "error:no_email"
    
    currency = user.local_currency or "NGN"
    price_usd = PaymentManager.PLANS.get(plan_name, {}).get(period, 0)
    rate = PaymentManager.RATES.get(currency, 1600)
    
    # Amount in smallest currency unit (kobo for NGN)
    amount = int(price_usd * rate * 100)
    
    paystack = PaystackPayment()
    result = await paystack.initialize_transaction(
        email=user.email,
        amount=amount,
        currency=currency,
        plan_name=plan_name,
        user_id=user.telegram_id,
        period=period
    )
    
    if result["success"]:
        # Store reference for verification
        context.user_data['pending_payment'] = {
            'reference': result['reference'],
            'plan': plan_name,
            'period': period
        }
        return result["authorization_url"]
    else:
        return f"error:{result.get('error', 'Unknown error')}"


async def activate_subscription(user_id: int, plan_name: str, period: str = "monthly") -> bool:
    """Activate user subscription after successful payment."""
    from src.database.db_manager import DatabaseManager
    
    db = DatabaseManager()
    
    # Calculate expiry
    if period == "yearly":
        expiry = datetime.utcnow() + timedelta(days=365)
    else:
        expiry = datetime.utcnow() + timedelta(days=30)
    
    # Update user plan
    session = db.get_session()
    try:
        from src.database.models import User, Plan
        user = session.query(User).filter(User.telegram_id == user_id).first()
        plan = session.query(Plan).filter(Plan.name == plan_name).first()
        
        if user and plan:
            user.plan_id = plan.id
            user.subscription_expiry = expiry
            session.commit()
            return True
    except Exception as e:
        print(f"Activation error: {e}")
        session.rollback()
    finally:
        session.close()
    
    return False
