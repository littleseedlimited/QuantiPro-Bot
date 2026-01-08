"""
Project Management Handlers for QuantiProBot.
Provides CRUD operations for saving, listing, loading, and deleting analysis projects.
"""
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from src.database.db_manager import DatabaseManager
from src.bot.constants import ACTION
import os


async def show_projects_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Display list of saved projects for the user."""
    user_id = update.effective_user.id
    db = DatabaseManager()
    
    tasks = db.get_user_tasks(user_id, limit=10)
    
    if not tasks:
        await update.message.reply_text(
            "📁 **My Projects**\n\n"
            "You have no saved projects yet.\n\n"
            "To save a project, start an analysis and use '💾 Save & Exit'.",
            parse_mode='Markdown',
            reply_markup=ReplyKeyboardMarkup([['◀️ Back to Menu']], resize_keyboard=True)
        )
        return ACTION
    
    # Build inline keyboard for project selection
    buttons = []
    
    # Header row
    buttons.append([InlineKeyboardButton("🔄 Refresh List", callback_data="project_refresh")])
    
    for task in tasks:
        # Format: "Study Title | Date"
        status_icon = "🟢" if task['status'] == 'saved' else "✅"
        # Use research title if available, else fallback title
        display_title = task['title']
        created_date = task['created'] # YYYY-MM-DD HH:MM
        
        label = f"{status_icon} {display_title} ({created_date})"
        # Action: Click to open options menu for this project
        buttons.append([InlineKeyboardButton(label, callback_data=f"project_options_{task['id']}")])
    
    buttons.append([InlineKeyboardButton("◀️ Back to Menu", callback_data="project_back")])
    
    await update.message.reply_text(
        "📁 **My Projects**\n\n"
        "Select a project to manage (Open, Rename, Delete):",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(buttons)
    )
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
        await query.message.delete()
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
        
        await query.message.edit_text(
            f"📁 **Manage Project**\n\n"
            f"**Title**: {task['title']}\n"
            f"**Created**: {task.get('created', 'N/A')}\n"
            f"**Status**: {task['status']}\n\n"
            "Select an action:",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        return ACTION

    elif data.startswith("project_verify_"):
        # Ask for confirmation before delete
        task_id = int(data.replace("project_verify_", ""))
        buttons = [
            [InlineKeyboardButton("❌ Yes, Delete Forever", callback_data=f"project_delete_{task_id}")],
            [InlineKeyboardButton("🔙 No, Cancel", callback_data=f"project_options_{task_id}")]
        ]
        await query.message.edit_text(
            "⚠️ **Confirm Deletion**\n\n"
            "Are you sure you want to delete this project? This action cannot be undone.",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        return ACTION

    elif data.startswith("project_rename_"):
        # Initiate rename flow (ask for text input)
        task_id = int(data.replace("project_rename_", ""))
        context.user_data['awaiting_rename'] = task_id
        
        await query.message.edit_text(
            "✏️ **Rename Project**\n\n"
            "Please type the new name for this project:",
            parse_mode='Markdown'
        )
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
        
        await query.message.edit_text(
            f"📂 **Project Loaded!**\n\n"
            f"📄 _{task['title']}_\n\n"
            "Your previous session has been restored. Continue your analysis!",
            parse_mode='Markdown'
        )
        
        # Show action menu
        from src.bot.handlers import show_action_menu
        await show_action_menu(update, context=context)
        return ACTION
    
    return ACTION
