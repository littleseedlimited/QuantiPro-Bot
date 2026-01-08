"""
Project Management Handlers for QuantiProBot.
Provides CRUD operations for saving, listing, loading, and deleting analysis projects.
"""
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from src.database.db_manager import DatabaseManager
from src.bot.constants import ACTION
from telegram.error import BadRequest
import os
import html


async def show_projects_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Display list of saved projects for the user."""
    user_id = update.effective_user.id
    db = DatabaseManager()
    
    tasks = db.get_user_tasks(user_id, limit=10)
    
    msg = update.effective_message
    
    # helper for cleanup
    if update.callback_query:
        # If triggered by callback, we might want to edit or delete/reply
        # Usually delete old menu and send new, or edit. 
        # But 'reply_text' works on effective_message too.
        # Let's clean up previous message to avoid clutter if desired, or just edit.
        pass

    if not tasks:
        text = (
            "📁 <b>My Projects</b>\n\n"
            "You have no saved projects yet.\n\n"
            "To save a project, start an analysis and use '💾 Save & Exit'."
        )
        try:
            if update.callback_query:
                await msg.edit_text(text, parse_mode='HTML', reply_markup=ReplyKeyboardMarkup([['◀️ Back to Menu']], resize_keyboard=True))
            else:
                 await msg.reply_text(text, parse_mode='HTML', reply_markup=ReplyKeyboardMarkup([['◀️ Back to Menu']], resize_keyboard=True))
        except BadRequest:
            pass
        return ACTION
    
    # Build inline keyboard for project selection
    buttons = []
    
    # Header row
    buttons.append([InlineKeyboardButton("🔄 Refresh List", callback_data="project_refresh")])
    
    for task in tasks:
        # Format: "Study Title | Date"
        status_icon = "🟢" if task['status'] == 'saved' else "✅"
    for task in tasks:
        # Format: "Study Title | Date"
        status_icon = "🟢" if task['status'] == 'saved' else "✅"
        # Use research title if available, else fallback title.
        # Button labels are PLAIN TEXT - NO ESCAPING NEEDED for Markdown/HTML
        display_title = task['title']
        created_date = task['created'] # YYYY-MM-DD HH:MM
        
        label = f"{status_icon} {display_title} ({created_date})"
        # Action: Click to open options menu for this project
        buttons.append([InlineKeyboardButton(label, callback_data=f"project_options_{task['id']}")])
    
    buttons.append([InlineKeyboardButton("◀️ Back to Menu", callback_data="project_back")])
    
    text = (
        "📁 <b>My Projects</b>\n\n"
        "Select a project to manage (Open, Rename, Delete):"
    )
    
    try:
        if update.callback_query:
            await msg.edit_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(buttons))
        else:
            await msg.reply_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(buttons))
    except BadRequest:
        pass
        
    return ACTION


async def save_current_project(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Save the current analysis session as a project."""
    user_id = update.effective_user.id
    db = DatabaseManager()
    
    # Gather context data
    file_path = context.user_data.get('file_path', '')
    research_title = context.user_data.get('research_title', 'Untitled Analysis')
    
    # Build context to save
    context_data = {
        'file_path': file_path,
        'research_title': context.user_data.get('research_title', ''),
        'research_objectives': context.user_data.get('research_objectives', ''),
        'research_questions': context.user_data.get('research_questions', ''),
        'research_hypothesis': context.user_data.get('research_hypothesis', ''),
        'columns': context.user_data.get('columns', []),
        'num_cols': context.user_data.get('num_cols', []),
        'analysis_history': context.user_data.get('analysis_history', []),
    }
    
    task_id = db.save_task(
        user_id=user_id,
        title=research_title or 'Untitled Analysis',
        file_path=file_path,
        context_data=context_data,
        status='saved'
    )
    
    await update.message.reply_text(
        f"💾 **Project Saved!**\n\n"
        f"📄 Title: _{research_title or 'Untitled Analysis'}_\n"
        f"🆔 Project ID: `{task_id}`\n\n"
        "You can resume this project anytime from '📁 My Projects'.",
        parse_mode='Markdown',
        reply_markup=ReplyKeyboardMarkup([
            ['📁 My Projects', '📊 Analyse Data (Upload File)'],
            ['🏠 Main Menu']
        ], resize_keyboard=True)
    )
    return ACTION


async def project_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline button callbacks for project operations."""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    db = DatabaseManager()
    data = query.data
    
    if data == "project_back" or data == "project_refresh":
        # Return to main project list
        # Don't delete, just passing control to show_projects_menu which handles edit/reply
        await show_projects_menu(update, context)
        return ACTION
    
    elif data.startswith("project_options_"):
        # Show CRUD Sub-menu for a specific project
        task_id = int(data.replace("project_options_", ""))
        task = db.get_task(task_id)
        
        if not task:
            await query.answer("Project not found.", show_alert=True)
            await show_projects_menu(update, context)
            return ACTION
            
        buttons = [
            [InlineKeyboardButton("📂 Open / Load", callback_data=f"project_load_{task_id}")],
            [InlineKeyboardButton("✏️ Rename", callback_data=f"project_rename_{task_id}")],
            [InlineKeyboardButton("🗑️ Delete", callback_data=f"project_verify_{task_id}")],
            [InlineKeyboardButton("◀️ Back to List", callback_data="project_refresh")]
        ]
        
        # Escape title for HTML
        safe_title = html.escape(task['title'])

        try:
            await query.message.edit_text(
                f"📁 <b>Manage Project</b>\n\n"
                f"<b>Title</b>: {safe_title}\n"
                f"<b>Created</b>: {task.get('created', 'N/A')}\n"
                f"<b>Status</b>: {task['status']}\n\n"
                "Select an action:",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup(buttons)
            )
        except BadRequest:
            pass
        return ACTION

    elif data.startswith("project_verify_"):
        # Ask for confirmation before delete
        task_id = int(data.replace("project_verify_", ""))
        buttons = [
            [InlineKeyboardButton("❌ Yes, Delete Forever", callback_data=f"project_delete_{task_id}")],
            [InlineKeyboardButton("🔙 No, Cancel", callback_data=f"project_options_{task_id}")]
        ]
        try:
            await query.message.edit_text(
                "⚠️ <b>Confirm Deletion</b>\n\n"
                "Are you sure you want to delete this project? This action cannot be undone.",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup(buttons)
            )
        except BadRequest:
            pass
        return ACTION

    elif data.startswith("project_rename_"):
        # Initiate rename flow (ask for text input)
        task_id = int(data.replace("project_rename_", ""))
        context.user_data['awaiting_rename'] = task_id
        
        try:
            await query.message.edit_text(
                "✏️ <b>Rename Project</b>\n\n"
                "Please type the new name for this project:",
                parse_mode='HTML'
            )
        except BadRequest:
             pass
        return ACTION
        return ACTION

    elif data.startswith("project_delete_"):
        # Actual Delete
        task_id = int(data.replace("project_delete_", ""))
        success = db.delete_task(task_id, user_id)
        
        if success:
            await query.answer("Project deleted successfully!", show_alert=True)
            await show_projects_menu(update, context)
        else:
            await query.answer("Could not delete project.", show_alert=True)
        return ACTION
    
    elif data.startswith("project_load_"):
        task_id = int(data.replace("project_load_", ""))
        task = db.get_task(task_id)
        
        if not task:
            await query.message.edit_text("❌ Project not found.")
            return ACTION
        
        # Restore context
        saved_context = task.get('context', {})
        for key, value in saved_context.items():
            context.user_data[key] = value
        
        # Mark as in_progress
        db.update_task_status(task_id, 'in_progress')
        
        # Escape title for HTML
        safe_title = html.escape(task['title'])
        
        try:
            await query.message.edit_text(
                f"📂 <b>Project Loaded!</b>\n\n"
                f"📄 <i>{safe_title}</i>\n\n"
                "Your previous session has been restored. Continue your analysis!",
                parse_mode='HTML'
            )
        except BadRequest:
            pass
        
        # Show action menu
        from src.bot.handlers import show_action_menu
        await show_action_menu(update, context=context)
        return ACTION
    
    return ACTION
