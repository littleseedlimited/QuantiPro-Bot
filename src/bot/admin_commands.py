from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from src.database.db_manager import DatabaseManager
from src.database.models import User
import logging

logger = logging.getLogger(__name__)

async def admin_users_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all users (Admin only)."""
    user_id = update.effective_user.id
    db = DatabaseManager()
    user = db.get_user(user_id)
    
    if not user or not user.is_admin:
        await update.message.reply_text("⛔ You are not authorized to use this command.")
        return

    session = db.get_session()
    users = session.query(User).all()
    
    msg = "👥 **User List**\n\n"
    for u in users:
        status = "🔴 BANNED" if getattr(u, 'is_banned', False) else "🟢 Active"
        plan = u.plan.name if u.plan else "None"
        msg += f"ID: `{u.telegram_id}` | {u.full_name}\n"
        msg += f"Plan: {plan} | Status: {status}\n"
        if u.username:
            msg += f"Username: @{u.username}\n"
        msg += "-------------------\n"
    
    # Split message if too long
    if len(msg) > 4000:
        for x in range(0, len(msg), 4000):
            await update.message.reply_text(msg[x:x+4000], parse_mode='Markdown')
    else:
        await update.message.reply_text(msg, parse_mode='Markdown')
    session.close()

async def admin_ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ban a user by ID."""
    if not context.args:
        await update.message.reply_text("Usage: /ban <user_id>")
        return

    target_id = context.args[0]
    db = DatabaseManager()
    
    # Check admin
    admin = db.get_user(update.effective_user.id)
    if not admin or not admin.is_admin:
        return

    session = db.get_session()
    target = session.query(User).filter(User.telegram_id == target_id).first()
    
    if target:
        target.is_banned = True
        session.commit()
        await update.message.reply_text(f"🚫 User {target.full_name} ({target_id}) has been BANNED.")
    else:
        await update.message.reply_text("User not found.")
    session.close()

async def admin_unban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Unban a user by ID."""
    if not context.args:
        await update.message.reply_text("Usage: /unban <user_id>")
        return

    target_id = context.args[0]
    db = DatabaseManager()
    
    # Check admin
    admin = db.get_user(update.effective_user.id)
    if not admin or not admin.is_admin:
        return

    session = db.get_session()
    target = session.query(User).filter(User.telegram_id == target_id).first()
    
    if target:
        target.is_banned = False
        session.commit()
        await update.message.reply_text(f"✅ User {target.full_name} ({target_id}) has been UNBANNED.")
    else:
        await update.message.reply_text("User not found.")
    session.close()

async def admin_delete_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Delete a user by ID."""
    if not context.args:
        await update.message.reply_text("Usage: /delete <user_id>")
        return

    target_id = context.args[0]
    db = DatabaseManager()
    
    # Check admin
    admin = db.get_user(update.effective_user.id)
    if not admin or not admin.is_admin:
        return

    session = db.get_session()
    target = session.query(User).filter(User.telegram_id == target_id).first()
    
    if target:
        try:
            session.delete(target)
            session.commit()
            await update.message.reply_text(f"🗑️ User {target_id} has been PERMANENTLY DELETED.")
        except Exception as e:
             await update.message.reply_text(f"Error deleting user: {e}")
    else:
        await update.message.reply_text("User not found.")
    session.close()

async def admin_upgrade_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Upgrade user plan: /upgrade <id> <plan_name>"""
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /upgrade <user_id> <plan_name>\nPlans: Free, Basic, Pro, Enterprise, Limitless")
        return

    target_id = context.args[0]
    plan_name = context.args[1]
    
    db = DatabaseManager()
    
    # Check admin
    admin = db.get_user(update.effective_user.id)
    if not admin or not admin.is_admin:
        return

    try:
        if db.update_user_plan(target_id, plan_name):
             await update.message.reply_text(f"✅ User {target_id} upgraded to {plan_name}.")
        else:
             await update.message.reply_text(f"❌ Failed. Check if plan '{plan_name}' exists.")
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")
