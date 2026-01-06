from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo, KeyboardButton
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, filters, CallbackQueryHandler
import pandas as pd
import os
import io
import asyncio
import gc
from openai import AsyncOpenAI

from src.core.file_manager import FileManager
from src.core.analyzer import Analyzer
from src.core.ai_interpreter import AIInterpreter
from src.core.visualizer import Visualizer
from src.bot.constants import (
    UPLOAD, ACTION, MANUSCRIPT_REVIEW, VISUAL_SELECT, SAVE_PROJECT,
    RESEARCH_TITLE, RESEARCH_OBJECTIVES, RESEARCH_QUESTIONS, RESEARCH_HYPOTHESIS,
    GOAL_SELECT, VAR_SELECT_1, VAR_SELECT_2, CONFIRM_ANALYSIS, POST_ANALYSIS
)
from src.bot.interview import InterviewManager
from src.bot.signup import SignupManager
from src.database.db_manager import DatabaseManager
from src.utils.logger import logger
import logging
from datetime import datetime

# Configuration
DATA_DIR = os.getenv("DATA_DIR", "data")
os.makedirs(DATA_DIR, exist_ok=True)


# Feature enforcement helper
async def check_feature(update: Update, user_id: int, feature: str, feature_label: str = None) -> bool:
    """
    Check if user's plan includes a feature. Returns True if allowed, False if blocked.
    Sends upgrade message if blocked.
    """
    db = DatabaseManager()
    user = db.get_user(user_id)
    
    if not user or not user.plan:
        return True  # Allow if no plan info (shouldn't happen)
    
    limits = user.plan.get_limits()
    
    # Check boolean features
    if feature in limits and isinstance(limits[feature], bool):
        if not limits[feature]:
            label = feature_label or feature.replace('_', ' ').title()
            await update.message.reply_text(
                f"🔒 **{label}** requires an upgrade.\n\n"
                f"📍 Your plan: **{user.plan.name}**\n"
                f"Use /plans to see available options.",
                parse_mode='Markdown'
            )
            return False
    
    return True


async def check_feature_limit(update: Update, user_id: int, feature: str, current: int, feature_label: str = None) -> bool:
    """
    Check if user has reached their feature limit. Returns True if under limit.
    """
    db = DatabaseManager()
    limit = db.get_user_feature_limit(user_id, feature, 9999)
    
    if current >= limit:
        user = db.get_user(user_id)
        label = feature_label or feature.replace('_', ' ').title()
        await update.message.reply_text(
            f"🔒 **{label} limit reached** ({current}/{limit})\n\n"
            f"📍 Your plan: **{user.plan.name if user and user.plan else 'Free'}**\n"
            f"Use /plans to upgrade.",
            parse_mode='Markdown'
        )
        return False
    
    return True



# Helper: Show action menu with navigation
async def show_action_menu(update: Update, message_prefix: str = "", context=None):
    menu_text = f"{message_prefix}\n\n**Main Menu - Select a Category:**" if message_prefix else "**Main Menu - Select a Category:**"
    
    # Use effective_message for both regular messages and callback queries
    message = update.effective_message
    
    web_app_url = os.getenv("MINIAPP_URL", "https://tomoko-pericarditic-regretfully.ngrok-free.dev/app")
    
    await message.reply_text(
        menu_text,
        parse_mode='Markdown',
        reply_markup=ReplyKeyboardMarkup([
            [KeyboardButton("🚀 Open Mini App", web_app=WebAppInfo(url=web_app_url))],
            ['📉 Describe & Explore', '🆚 Hypothesis Tests'],
            ['🔗 Relationships & Models', '📝 Generate Report'],
            ['💬 AI Chat', '📁 My Projects'],
            ['💾 Save & Exit', '👤 My Profile'],
            ['💳 Subscription', '❌ Cancel']
        ], one_time_keyboard=False, resize_keyboard=True)
    )

def get_column_markup(cols, max_cols=30, back_label='◀️ Back to Menu', extra_buttons=None, selected_items=None):
    """Helper to create a limited variable selection keyboard to avoid Telegram limits."""
    selected_items = selected_items or []
    items = []
    
    # Humanize labels for display (remove .1 suffixes if they somehow persisted)
    import re
    
    for c in list(cols)[:max_cols]:
        display_label = str(c)
        if '.' in display_label:
            # If it's a pandas-style duplicate (e.g. Var.1), make it prettier
            display_label = re.sub(r'\.(\d+)$', r' (Dup \1)', display_label)
            
        label = f"✅ {display_label}" if c in selected_items else display_label
        items.append(label)
        
    keyboard = []
    for i in range(0, len(items), 2):
        keyboard.append(items[i:i+2])
    
    final_row = []
    if extra_buttons:
        final_row.extend(extra_buttons)
    if back_label:
        final_row.append(back_label)
    
    if final_row:
        keyboard.append(final_row)
        
    return ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)

async def force_admin_init(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Temporary command to force admin rights for debugging."""
    user_id = update.effective_user.id
    username = update.effective_user.username
    print(f"DEBUG: Force Admin triggered by {user_id} (@{username})")
    
    if username and username.lower() == "origichidiah":
        db = DatabaseManager()
        db.set_admin(user_id, True)
        db.update_user_plan(user_id, "Limitless")
        await update.message.reply_text(f"✅ Forced Admin Rights for @{username}\nMode: Limitless\nAdmin: True")
    else:
        await update.message.reply_text(f"❌ Username mismatch. You refer as: @{username}")


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        print(f"--- START HANDLER TRIGGERED FOR {user_id} ---")
        db = DatabaseManager()
        user = db.get_user(user_id)

        # Super Admin Check (Username based + Env ID)
        current_username = update.effective_user.username
        admin_id = os.getenv("SUPER_ADMIN_ID")
        
        is_super_admin = False
        if current_username and current_username.lower() == "origichidiah":
            is_super_admin = True
        elif admin_id and str(user_id) == str(admin_id):
            is_super_admin = True

        if is_super_admin:
            if not user:
                print("DEBUG: Registering super admin")
                user = db.create_user(user_id, full_name="Super Admin", is_admin=True)
                db.update_user_plan(user_id, "Limitless") 
                user = db.get_user(user_id) 
            elif not user.is_admin or user.plan.name != "Limitless":
                print("DEBUG: Updating super admin plan")
                user.is_admin = True
                db.update_user_plan(user_id, "Limitless")
                user = db.get_user(user_id) 

        # Check if user is banned
        if user and getattr(user, 'is_banned', False):
            await update.message.reply_text(
                "🚫 **Access Denied**\n\n"
                "Your account has been suspended by the administrator.",
                parse_mode='Markdown'
            )
            return ConversationHandler.END

        if not user:
            print(f"DEBUG: User {user_id} not found, redirecting to signup")
            return await SignupManager.start_signup(update, context)

        # MAIN MENU: Choice between Analysis, Sampling, and Projects
        # MAIN MENU: Choice between Analysis, Sampling, and Projects
        # WebApp URI
        # WebApp URI
        # Dynamic Ngrok URL Discovery
        web_app_url = os.getenv("MINIAPP_URL")
        
        # Try to fetch from local ngrok API if no env var
        if not web_app_url:
            try:
                async with httpx.AsyncClient() as client:
                    resp = await client.get("http://localhost:4040/api/tunnels", timeout=2.0)
                    if resp.status_code == 200:
                        data = resp.json()
                        public_url = data['tunnels'][0]['public_url']
                        web_app_url = f"{public_url}/app"
                        print(f"DEBUG: Discovered ngrok URL: {web_app_url}")
            except Exception as e:
                print(f"DEBUG: Could not fetch ngrok URL: {e}")
        
        # Fallback if discovery fails
        if not web_app_url:
             web_app_url = "https://tomoko-pericarditic-regretfully.ngrok-free.dev/app"

        await update.message.reply_text(
            f"👋 **Welcome back, {user.full_name}!**\n\n"
            "What would you like to do today?",
            reply_markup=ReplyKeyboardMarkup([
                [KeyboardButton("🚀 Open Mini App", web_app=WebAppInfo(url=web_app_url))],
                ['📊 Analyse Data (Upload File)', '🔢 Calculate Sample Size'],
                ['📁 My Projects', '👤 My Profile'],
                ['💳 Subscription']
            ], one_time_keyboard=False, resize_keyboard=True),
            parse_mode='Markdown'
        )
        return ACTION  # We reuse ACTION state to route this initial choice
        
    except Exception as e:
        print(f"!!! CRITICAL ERROR IN START_HANDLER: {e}")
        import traceback
        traceback.print_exc()
        logger.error(f"Error in start_handler: {e}", exc_info=True)
        if update.message:
            await update.message.reply_text("⚠️ An internal error occurred. Please check the terminal for logs.")
        return ConversationHandler.END

async def file_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    file_obj = update.message.document
    
    if not file_obj:
        await update.message.reply_text("Please upload a document file.")
        return UPLOAD

    user_id = update.message.from_user.id
    db = DatabaseManager()
    user_db = db.get_user(user_id)
    
    if not user_db:
        await update.message.reply_text("⚠️ **Registration Required**\n\nYou must sign up before uploading data for analysis.", parse_mode='Markdown')
        return await SignupManager.start_signup(update, context)

    file_name = file_obj.file_name
    file_id = file_obj.file_id
    
    # Download file
    new_file = await context.bot.get_file(file_id)
    file_path = os.path.join(DATA_DIR, f"{user.id}_{file_name}")
    await new_file.download_to_drive(file_path)
    
    # Check if this is a reference file upload
    if context.user_data.get('awaiting_reference_file'):
        context.user_data['awaiting_reference_file'] = False
        
        from src.writing.citations import ReferenceParser
        
        refs, status_msg = ReferenceParser.parse_file(file_path)
        
        if refs:
            # Store references in context
            if 'references' not in context.user_data:
                context.user_data['references'] = []
            context.user_data['references'].extend(refs)
            
            # Show preview
            preview_lines = []
            for i, ref in enumerate(refs[:5], 1):
                authors_str = ref.authors[0] if ref.authors else "Unknown"
                preview_lines.append(f"{i}. {authors_str} ({ref.year}). {ref.title[:50]}...")
            
            preview = "\n".join(preview_lines)
            total = len(context.user_data['references'])
            
            await update.message.reply_text(
                f"✅ **References Imported Successfully!**\n\n"
                f"📊 {status_msg}\n\n"
                f"**Preview:**\n{preview}\n\n"
                f"📚 **Total references in session:** {total}\n\n"
                "*References will be included in your generated report.*",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                f"⚠️ Could not parse references from this file.\n\n{status_msg}\n\n"
                "Please ensure the file is in a supported format (RIS, BibTeX, etc.)"
            )
        
        await show_action_menu(update)
        return ACTION
    
    # Store in context (for data files)
    context.user_data['file_path'] = file_path
    
    try:
        # Load Data
        df, meta = FileManager.load_file(file_path)
        
        # Tier Enforcement from DB
        db = DatabaseManager()
        user = db.get_user(update.message.from_user.id)
        row_limit = user.plan.row_limit if user else 150
        
        if df.shape[0] > row_limit:
             await update.message.reply_text(
                 f"⚠️ **Limit Exceeded!**\n\nYour **{user.plan.name}** plan supports up to {row_limit} rows. Your file has {df.shape[0]} rows.\n"
                 "Please upgrade your plan to process more data.",
                 parse_mode='Markdown'
             )
             return UPLOAD

        # Automated Cleaning
        df = FileManager.clean_data(df)
        
        # Initialize session tracking
        context.user_data['analysis_history'] = []
        context.user_data['visuals_history'] = []
        
        context.user_data['columns'] = list(df.columns)
        context.user_data['num_cols'] = df.select_dtypes(include=['number']).columns.tolist()

        info = FileManager.get_file_info(df)
        
        # SAVE SESSION FOR MINIAPP MIRRORING
        db.save_active_session(
            user_id=user_id, 
            file_path=file_path, 
            context_data={
                'columns': list(df.columns),
                'rows': len(df)
            }
        )
        
        await update.message.reply_text(
            f"✅ **File Loaded & Cleaned Successfully!**\n\n{info}\n\n"
            "**Would you like to map variable labels?**\n"
            "_Define value labels (e.g., 1=Male) for better charts & reports._",
            parse_mode='Markdown',
            reply_markup=ReplyKeyboardMarkup([
                ['Yes, Map Labels', 'No, Proceed']
            ], one_time_keyboard=True, resize_keyboard=True)
        )
        context.user_data['awaiting_map_decision'] = True
        return ACTION

        
    except Exception as e:
        await update.message.reply_text(f"❌ Error loading file: {str(e)}\nPlease try another file.")
        return UPLOAD

async def action_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Main handler for routing menu actions and text inputs.
    """
    if not update.message or not update.message.text:
         return ACTION
         
    choice = update.message.text
    file_path = context.user_data.get('file_path')
    df = context.user_data.get('df')

    # --- HANDLE UPLOAD DECISION ---
    if context.user_data.get('awaiting_map_decision'):
        context.user_data['awaiting_map_decision'] = False
        
        if choice == 'Yes, Map Labels':
            # Redirect to mapping flow
            context.user_data['awaiting_map_col'] = True
            if df is not None:
                cols = df.columns.tolist()
                keyboard = [[c] for c in cols[:20]]
                keyboard.append(['◀️ Back'])
                await update.message.reply_text(
                    "🏷️ **Select Variable to Label**\nChoose the column containing values (e.g., 1, 2) you want to rename:",
                    reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
                )
                return ACTION
        
        elif choice == 'No, Proceed':
            # Show Dataset Description & Main Menu
            if df is not None:
                # Create a readable summary
                num_vars = len(df.select_dtypes(include='number').columns)
                cat_vars = len(df.select_dtypes(exclude='number').columns)
                
                desc = f"📊 **Dataset Overview**\n"
                desc += f"• **Rows**: {len(df):,}\n"
                desc += f"• **Columns**: {len(df.columns)}\n"
                desc += f"• **Numeric Vars**: {num_vars}\n"
                desc += f"• **Categorical Vars**: {cat_vars}\n\n"
                desc += "**Top Variables:**\n"
                for col in df.columns[:5]:
                    dtype = str(df[col].dtype)
                    desc += f"- `{col}` ({dtype})\n"
                
                await update.message.reply_text(desc, parse_mode='Markdown')
            
            await show_action_menu(update)
            return ACTION

    # --- MAIN MENU ROUTING (Pre-File Load) ---
    if choice == '📊 Analyse Data (Upload File)':
        # Reset project state for new analysis
        for key in ['research_title', 'research_objectives', 'research_questions', 'research_hypothesis', 'analysis_history', 'visuals_history']:
            context.user_data.pop(key, None)
        
        context.user_data['next_step'] = 'upload'
        from src.bot.interview import InterviewManager
        print(f"DEBUG: Starting interview for {context.user_data['next_step']}")
        return await InterviewManager.start_interview(update, context)

    if choice == '🔢 Calculate Sample Size':
        # Reset project state for new sampling
        for key in ['research_title', 'research_objectives', 'research_questions', 'research_hypothesis']:
            context.user_data.pop(key, None)
            
        context.user_data['next_step'] = 'sampling'
        from src.bot.interview import InterviewManager
        print(f"DEBUG: Starting interview for {context.user_data['next_step']}")
        return await InterviewManager.start_interview(update, context)
    if choice == '👤 My Profile':
         from src.bot.handlers import profile_handler
         await profile_handler(update, context)
         return ACTION
    if choice == '💳 Subscription':
         from src.bot.handlers import myplan_handler
         await myplan_handler(update, context)
         return ACTION
    
    if choice == '📁 My Projects':
        from src.bot.project_handlers import show_projects_menu
        return await show_projects_menu(update, context)
    
    if choice == '💾 Save & Exit':
        from src.bot.project_handlers import save_current_project
        return await save_current_project(update, context)
    # -------------------------

    # --- HANDLE AI CHAT MODE FIRST (before other resets) ---
    if context.user_data.get('ai_chat_mode'):
        if choice == 'Exit Chat' or choice.lower() == 'exit':
            context.user_data['ai_chat_mode'] = False
            await show_action_menu(update, "Exited AI Chat.")
            return ACTION
        
        # Process AI query about data
        try:
            msg_handle = await update.message.reply_text("🤖 Processing your request... (this may take up to 30s)")
            
            # Use pre-loaded df
            df = context.user_data.get('df')
            if df is None and file_path and os.path.exists(file_path):
                df, _ = FileManager.load_file(file_path)
            
            # Build context for AI
            if df is not None:
                data_summary = f"Dataset: {len(df)} rows, {len(df.columns)} columns\n"
                data_summary += f"Columns: {', '.join(df.columns.tolist())}\n"
                num_cols = df.select_dtypes(include='number').columns.tolist()
                data_summary += f"Numeric: {', '.join(num_cols[:50])}" 
            else:
                data_summary = "No dataset loaded. Answering as a general statistics assistant."
            
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                await msg_handle.edit_text("❌ Error: OpenAI API Key not configured.")
                return ACTION

            client = AsyncOpenAI(api_key=api_key)
            
            try:
                response = await client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": f"You are a statistical analyst assistant. The user has a dataset with these details:\n{data_summary}\n\nAnswer their question about the data or statistics in general. Be clear and helpful. Format your response nicely for Telegram."},
                        {"role": "user", "content": choice}
                    ],
                    max_tokens=500,
                    timeout=25.0
                )
                answer = response.choices[0].message.content
                
                await msg_handle.delete()
                await update.message.reply_text(f"🤖 **AI Response:**\n\n{answer}", parse_mode='Markdown')
                
            except asyncio.TimeoutError:
                await msg_handle.edit_text("⚠️ AI Request Timed Out. Please try again or ask a simpler question.")
                return ACTION
            except Exception as ai_err:
                await msg_handle.edit_text(f"⚠️ AI Error: {str(ai_err)[:100]}")
                return ACTION

            await update.message.reply_text(
                "Ask another question or:",
                reply_markup=ReplyKeyboardMarkup([['Exit Chat']], one_time_keyboard=True, resize_keyboard=True)
            )
        except Exception as e:
            await update.message.reply_text(f"System Error: {str(e)[:100]}\n\nTry a simpler question.")
        
        return ACTION

    # --- RESET STICKY STATES (only if NOT in AI chat mode) ---
    context.user_data['awaiting_column_select'] = None

    # --- VARIABLE LABEL MAPPING ---
    if choice == '🏷️ Map Variable Labels':
        # Prompt for variable selection (using existing helper if possible, or manual list)
        if df is None:
            await update.message.reply_text("⚠️ Please upload data first.")
            return ACTION
            
        context.user_data['awaiting_map_col'] = True
        cols = df.columns.tolist()
        # Simple keyboard
        keyboard = [[c] for c in cols[:20]]
        keyboard.append(['◀️ Back'])
        await update.message.reply_text(
            "🏷️ **Select Variable to Label**\nChoose the column containing values (e.g., 1, 2) you want to rename:",
            reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
        )
        return ACTION

    if context.user_data.get('awaiting_map_col'):
        if choice == '◀️ Back':
            context.user_data['awaiting_map_col'] = False
            await show_action_menu(update)
            return ACTION
            
        context.user_data['map_target_col'] = choice
        context.user_data['awaiting_map_col'] = False
        context.user_data['awaiting_map_values'] = True
        
        await update.message.reply_text(
            f"📝 **Enter Labels for '{choice}'**\n\n"
            "Format: `Value=Label, Value=Label`\n"
            "Example: `1=Male, 2=Female`\n\n"
            "Type the mapping below:",
            parse_mode='Markdown',
            reply_markup=ReplyKeyboardMarkup([['◀️ Cancel']], one_time_keyboard=True)
        )
        return ACTION

    if context.user_data.get('awaiting_map_values'):
        if choice == '◀️ Cancel':
            context.user_data['awaiting_map_values'] = False
            await show_action_menu(update)
            return ACTION
            
        from src.core.data_mapper import DataMapper
        target_col = context.user_data.get('map_target_col')
        
        try:
            mapping = DataMapper.parse_mapping_string(choice)
            if mapping:
                df = context.user_data['df']
                df = DataMapper.apply_mapping(df, target_col, mapping)
                context.user_data['df'] = df # Update session df
                
                await update.message.reply_text(
                    f"✅ Updated **{target_col}**!\n"
                    f"Mapped: {mapping}\n\n"
                    "You can now use these labels in charts and tables."
                )
            else:
                await update.message.reply_text("⚠️ Could not parse mapping. Try '1=A, 2=B'.")
        except Exception as e:
            await update.message.reply_text(f"⚠️ Error: {e}")
            
        context.user_data['awaiting_map_values'] = False
        await show_action_menu(update)
        return ACTION
    if choice == '📉 Describe & Explore':
        await update.message.reply_text(
            "📉 **Describe & Explore**\n_Select an analysis type:_ ",
            parse_mode='Markdown',
            reply_markup=ReplyKeyboardMarkup([
                ['📊 Descriptive Stats', '📋 Frequencies'],
                ['🔗 Reliability Analysis', '📊 Tabulation'],
                ['◀️ Back to Menu']
            ], one_time_keyboard=True, resize_keyboard=True)
        )
        return ACTION

    if choice == '🆚 Hypothesis Tests':
        from src.bot.analysis_handlers import start_hypothesis
        return await start_hypothesis(update, context)

    if choice == '🔗 Relationships & Models':
        await update.message.reply_text(
            "🔗 **Relationships & Models**\n_Select an analysis type:_ ",
            parse_mode='Markdown',
            reply_markup=ReplyKeyboardMarkup([
                ['📈 Correlation', '📉 Regression'],
                ['🎲 Crosstab', '🎨 Visuals'],
                ['◀️ Back to Menu']
            ], one_time_keyboard=True, resize_keyboard=True)
        )
        return ACTION

    if choice == '❌ Cancel':
        await update.message.reply_text("Cancelled. Use /start to restart.", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END

    if choice == '◀️ Back to Menu':
        await update.message.reply_text(
            "**Select an Analysis Category:**",
            parse_mode='Markdown',
            reply_markup=ReplyKeyboardMarkup([
                ['📉 Describe & Explore', '🆚 Hypothesis Tests'],
                ['🔗 Relationships & Models', '📝 Generate Report'],
                ['🏷️ Map Variable Labels', '💬 AI Chat', '❌ Cancel']
            ], one_time_keyboard=True, resize_keyboard=True)
        )
        return ACTION

    # --- DATA LOADING (Only needed for actual analysis actions) ---
    df = None
    if file_path and os.path.exists(file_path):
        try:
            df, _ = FileManager.load_file(file_path)
            # Recover critical context if missing
            if 'num_cols' not in context.user_data or not context.user_data['num_cols']:
                df = FileManager.clean_data(df)
                context.user_data['columns'] = list(df.columns)
                context.user_data['num_cols'] = df.select_dtypes(include=['number']).columns.tolist()
            context.user_data['df'] = df
        except Exception as e:
            logger.error(f"Error loading file: {e}")
            await update.message.reply_text("⚠️ **File Error**\n\nCould not load your data. Please upload again.", parse_mode='Markdown')
            return UPLOAD
    
    # Check if data is needed for this action
    data_required_actions = [
        'Descriptive Stats', 'Frequencies', 'Reliability Analysis', 'Tabulation',
        'Correlation', 'Regression', 'Crosstab', 'Visuals', '📝 Generate Report'
    ]
    if choice in data_required_actions and df is None:
        await update.message.reply_text(
            "⚠️ **No Active Data**\n\nPlease upload a file first.",
            parse_mode='Markdown',
            reply_markup=ReplyKeyboardMarkup([['📊 Analyse Data (Upload File)']], resize_keyboard=True)
        )
        return ACTION
    
    if choice == '💬 AI Chat':
        context.user_data['ai_chat_mode'] = True
        await update.message.reply_text(
            "**AI Analysis Chat**\n\nAsk me anything about your data (or general stats questions)!\n\nType 'Exit Chat' to return.",
            parse_mode='Markdown',
            reply_markup=ReplyKeyboardMarkup([['Exit Chat']], one_time_keyboard=True, resize_keyboard=True)
        )
        return ACTION


    # --- EXPORT HANDLERS ---
    if choice in ['📤 Export to Excel', '📤 Export to CSV']:
        last_analysis = context.user_data.get('last_analysis')
        if not last_analysis:
            await update.message.reply_text("❌ No analysis to export. Run an analysis first.")
            return ACTION
        
        try:
            import tempfile
            from datetime import datetime
            
            data = last_analysis['data']
            title = last_analysis['title']
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            # Convert to DataFrame if needed
            if isinstance(data, dict):
                export_df = pd.DataFrame(data)
            elif isinstance(data, pd.DataFrame):
                export_df = data
            else:
                export_df = pd.DataFrame([data])
            
            if choice == '📤 Export to Excel':
                with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp:
                    export_df.to_excel(tmp.name, index=True, sheet_name=title[:30])
                    tmp_path = tmp.name
                await update.message.reply_document(
                    document=open(tmp_path, 'rb'),
                    filename=f"{title.replace(' ', '_')}_{timestamp}.xlsx",
                    caption=f"📊 {title} - Exported"
                )
            else:  # CSV
                with tempfile.NamedTemporaryFile(suffix='.csv', delete=False, mode='w', encoding='utf-8') as tmp:
                    export_df.to_csv(tmp.name, index=True)
                    tmp_path = tmp.name
                await update.message.reply_document(
                    document=open(tmp_path, 'rb'),
                    filename=f"{title.replace(' ', '_')}_{timestamp}.csv",
                    caption=f"📊 {title} - Exported"
                )
            
            # Clean up temp file
            try:
                os.remove(tmp_path)
            except: pass
            
        except Exception as e:
            logger.error(f"Export error: {e}")
            await update.message.reply_text(f"❌ Export failed: {str(e)}")
        
        await update.message.reply_text(
            "Export complete!", 
            reply_markup=ReplyKeyboardMarkup([
                ['📉 Describe & Explore', '◀️ Back to Menu']
            ], one_time_keyboard=True, resize_keyboard=True)
        )
        return ACTION

    # --- SPECIFIC ACTIONS ---

    # --- ROUTE TO GUIDED ANALYSIS ---
    analysis_map = {
        '📊 Descriptive Stats': 'descriptive',
        '📋 Frequencies': 'frequencies',
        '🔗 Reliability Analysis': 'reliability',
        '📈 Correlation': 'correlation',
        '📉 Regression': 'regression',
        '🎲 Crosstab': 'crosstab',
        '📊 Tabulation': 'frequencies'
    }
    
    for icon_label, test_key in analysis_map.items():
        if choice == icon_label or choice == icon_label.split(' ', 1)[-1]:
            from src.bot.analysis_handlers import show_guide
            return await show_guide(update, context, test_key)

    # Legacy fallback for buttons without icons
    legacy_keys = {
        'Descriptive Stats': 'descriptive',
        'Reliability Analysis': 'reliability',
        'Correlation': 'correlation',
        'Regression': 'regression',
        'Crosstab': 'crosstab',
        'Frequencies': 'frequencies',
        'Tabulation': 'frequencies'
    }
    if choice in legacy_keys:
        from src.bot.analysis_handlers import show_guide
        return await show_guide(update, context, legacy_keys[choice])

    if choice == '🎨 Visuals' or choice == 'Visuals':
        return await visual_select_handler(update, context)

    # 5. REGRESSION (Fallthrough)
    if choice == 'Regression':
        pass # Let it fall through to the robust legacy handler below

    # -------------------------
    
    # CLEAR STICKY FLAGS if a main menu button is clicked
    main_menu_buttons = [
        'Interview Mode', 'Interview Mode (Guided)', 'AI Chat',
        'Descriptive Stats', 'Correlation', 'Tabulation', 'Crosstab',
        'Regression', 'Create Visuals', 'Generate Report', 'Upload References',
        'Save & Exit', 'Cancel', 'Clean & Sort Data', 'Show Data Table'
    ]
    if choice in main_menu_buttons:
        context.user_data['ai_chat_mode'] = False
        awaiting_keys = [k for k in context.user_data.keys() if k.startswith('awaiting_')]
        for k in awaiting_keys:
            context.user_data[k] = False
    
    # Handle profile editing
    if context.user_data.get('editing_field'):
        field = context.user_data['editing_field']
        context.user_data['editing_field'] = None
        
        if choice.lower() == 'cancel':
            await update.message.reply_text("Profile edit cancelled. Use /profile to view your profile.")
            return ACTION
        
        user_id = update.message.from_user.id
        db = DatabaseManager()
        
        field_map = {
            'name': 'full_name',
            'email': 'email',
            'phone': 'phone',
            'country': 'country'
        }
        
        db_field = field_map.get(field, field)
        db.update_user_profile(user_id, **{db_field: choice})
        
        await update.message.reply_text(
            f"Profile updated!\n\n{field.title()}: {choice}\n\nUse /profile to see your full profile."
        )
        return ACTION
    
    # Check if we need to show menu after loading a saved project
    if context.user_data.get('show_menu_on_next'):

        context.user_data['show_menu_on_next'] = False
        
        # Show project summary and action menu
        task_id = context.user_data.get('loaded_task_id', 'N/A')
        title = context.user_data.get('research_title', 'Untitled')
        analyses = len(context.user_data.get('analysis_history', []))
        refs = len(context.user_data.get('references', []))
        
        await update.message.reply_text(
            f"📂 **Continuing Project #{task_id}**\n\n"
            f"📝 Title: {title}\n"
            f"📊 Analyses: {analyses} | 📚 Refs: {refs}\n\n"
            "What would you like to do?",
            parse_mode='Markdown'
        )
        await show_action_menu(update)
        return ACTION
    
    if choice == 'Interview Mode' or choice == 'Interview Mode (Guided)':
        return await InterviewManager.start_interview(update, context)

    elif choice == 'AI Chat':
        context.user_data['ai_chat_mode'] = True
        await update.message.reply_text(
            "**AI Analysis Chat**\n\n"
            "Ask me anything about your data! Examples:\n"
            "- What is the mean age by gender?\n"
            "- Is there a correlation between X and Y?\n"
            "- Run a t-test comparing groups\n"
            "- Summarize my data\n\n"
            "Type your question or 'Exit Chat' to return:",
            parse_mode='Markdown',
            reply_markup=ReplyKeyboardMarkup([['Exit Chat']], one_time_keyboard=True)
        )
        return ACTION

    elif context.user_data.get('ai_chat_mode'):
        if choice == 'Exit Chat' or choice.lower() == 'exit':
            context.user_data['ai_chat_mode'] = False
            await show_action_menu(update, "Exited AI Chat.")
            return ACTION
        
        # Process AI query about data
        try:
            msg_handle = await update.message.reply_text("Processing your request... (this may take up to 30s)")
            
            # Use pre-loaded df
            if df is None:
                await msg_handle.edit_text("⚠️ Dataset not available. Please re-upload.")
                return ACTION
            
            # Build context for AI
            data_summary = f"Dataset: {len(df)} rows, {len(df.columns)} columns\n"
            data_summary += f"Columns: {', '.join(df.columns.tolist())}\n"
            
            # Add Data Snapshot (First 5 rows) for better context
            try:
                snapshot = df.head(5).to_markdown(index=False)
                data_summary += f"\nData Snapshot (First 5 rows):\n{snapshot}\n"
            except:
                pass

            # Add Analysis History
            history = context.user_data.get('analysis_history', [])
            if history:
                data_summary += "\nAnalyses Performed:\n"
                for h in history[-3:]: # Last 3 only
                    data_summary += f"- {h['test']}: {str(h.get('result', ''))[:100]}...\n"

            # Limit numeric cols string to avoid token limit
            num_cols = df.select_dtypes(include='number').columns.tolist()
            data_summary += f"\nNumeric Vars: {', '.join(num_cols[:50])}" 
            
            # from openai import AsyncOpenAI
            # import os
            # import asyncio
            
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                await msg_handle.edit_text("❌ Error: OpenAI API Key not configured.")
                return ACTION

            client = AsyncOpenAI(api_key=api_key)
            
            try:
                response = await client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": f"You are a statistical analyst. The user has a dataset:\n{data_summary}\n\nAnswer their question. Refer to the data snapshot/history if relevant. Be concise. Plain text only (no markdown tables)."},
                        {"role": "user", "content": choice}
                    ],
                    max_tokens=400,
                    timeout=30.0
                )
                answer = response.choices[0].message.content
                
                # Clean any remaining markdown
                import re
                answer = re.sub(r'\*\*([^*]+)\*\*', r'\1', answer)
                answer = re.sub(r'\*([^*]+)\*', r'\1', answer)
                
                await msg_handle.delete() # Remove "Processing..."
                await update.message.reply_text(f"Analysis Result:\n\n{answer}")
                
            except asyncio.TimeoutError:
                await msg_handle.edit_text("⚠️ AI Request Timed Out. Please try again or ask a simpler question.")
                return ACTION
            except Exception as ai_err:
                await msg_handle.edit_text(f"⚠️ AI Error: {str(ai_err)[:100]}")
                return ACTION

            await update.message.reply_text(
                "Ask another question or:",
                reply_markup=ReplyKeyboardMarkup([['Exit Chat']], one_time_keyboard=True)
            )
        except Exception as e:
            await update.message.reply_text(f"System Error: {str(e)[:100]}\n\nTry a simpler question.")
        
        return ACTION

    # Handle Regression Analysis
    elif choice == 'Regression':
        all_cols = context.user_data.get('columns', [])
        num_cols = context.user_data.get('num_cols', [])
        
        await update.message.reply_text(
            "**Regression Analysis**\n\n"
            "Select regression type:",
            parse_mode='Markdown',
            reply_markup=ReplyKeyboardMarkup([
                ['Linear Regression', 'Logistic Regression'],
                ['Multiple Regression'],
                ['Back to Menu']
            ], one_time_keyboard=True)
        )
        context.user_data['awaiting_regression_type'] = True
        return ACTION

    # Handle regression type selection
    elif context.user_data.get('awaiting_regression_type'):
        context.user_data['awaiting_regression_type'] = False
        
        if choice == 'Back to Menu':
            await show_action_menu(update)
            return ACTION
        
        context.user_data['regression_type'] = choice.lower().replace(' ', '_')
        num_cols = context.user_data.get('num_cols', [])
        all_cols = context.user_data.get('columns', [])
        
        cols_to_show = num_cols if 'logistic' not in choice.lower() else all_cols
        markup = get_column_markup(cols_to_show, back_label='Back to Menu')
        
        await update.message.reply_text(
            f"**{choice}**\n\n"
            "Select the DEPENDENT variable (outcome):",
            parse_mode='Markdown',
            reply_markup=markup
        )
        context.user_data['awaiting_regression_dep'] = True
        return ACTION

    # Handle regression dependent variable
    elif context.user_data.get('awaiting_regression_dep'):
        context.user_data['awaiting_regression_dep'] = False
        
        if choice == 'Back to Menu':
            await show_action_menu(update)
            return ACTION
        
        context.user_data['regression_dep_var'] = choice
        num_cols = context.user_data.get('num_cols', [])
        all_cols = context.user_data.get('columns', [])
        
        context.user_data['regression_ind_vars'] = []
        markup = get_column_markup(all_cols, back_label='Back to Menu', extra_buttons=['Done Selecting'])
        
        await update.message.reply_text(
            f"Dependent: {choice}\n\n"
            "Select INDEPENDENT variable(s):\n"
            "Tap each variable, then 'Done Selecting'",
            parse_mode='Markdown',
            reply_markup=markup
        )
        context.user_data['awaiting_regression_ind'] = True
        return ACTION

    # Handle regression independent variables
    elif context.user_data.get('awaiting_regression_ind'):
        if choice == 'Back to Menu':
            context.user_data['awaiting_regression_ind'] = False
            await show_action_menu(update)
            return ACTION
        
        if choice == 'Done Selecting':
            context.user_data['awaiting_regression_ind'] = False
            ind_vars = context.user_data.get('regression_ind_vars', [])
            
            if not ind_vars:
                await update.message.reply_text("Please select at least one independent variable.")
                return ACTION
            
            # Run regression
            await update.message.reply_text("Running regression analysis...")
            
            try:
                # df is pre-loaded at method start
                if df is None:
                    raise ValueError("Dataset not loaded. Please upload a file.")
                    
                dep_var = context.user_data.get('regression_dep_var')
                reg_type = context.user_data.get('regression_type', 'linear')
                
                if 'logistic' in reg_type:
                    result = Analyzer.run_logistic_regression(df, ind_vars, dep_var)
                else:
                    # Fix: run_linear_regression does not exist, use run_regression
                    # Signature: df, x_cols, y_col
                    result = Analyzer.run_regression(df, ind_vars, dep_var)
                
                if 'error' in result:
                    await update.message.reply_text(f"Error: {result['error']}")
                else:
                    # Format results as table
                    output = f"**Regression Results**\n"
                    output += f"Dependent: {dep_var}\n"
                    output += f"Type: {reg_type.replace('_', ' ').title()}\n\n"
                    
                    if 'logistic' in reg_type:
                        output += f"Pseudo R2: {result.get('pseudo_r2', 'N/A'):.4f}\n\n"
                    else:
                        output += f"R-squared: {result.get('r_squared', 'N/A'):.4f}\n\n"
                    
                    output += "```\n"
                    output += f"{'Variable':<15} {'Coef':<10} {'p-value':<10}\n"
                    output += "-" * 35 + "\n"
                    
                    params = result.get('params', {})
                    pvals = result.get('pvalues', {})
                    
                    for var in params:
                        coef = params[var]
                        pval = pvals.get(var, 'N/A')
                        sig = "*" if isinstance(pval, float) and pval < 0.05 else ""
                        output += f"{var:<15} {coef:<10.4f} {pval:<10.4f}{sig}\n"
                    
                    output += "```\n* p < 0.05"
                    
                    await update.message.reply_text(output, parse_mode='Markdown')
                    
            except Exception as e:
                await update.message.reply_text(f"Error: {str(e)[:100]}")
            
            await show_action_menu(update)
            return ACTION
        
        # Add variable to list
        if 'regression_ind_vars' not in context.user_data:
            context.user_data['regression_ind_vars'] = []
        
        if choice not in context.user_data['regression_ind_vars']:
            context.user_data['regression_ind_vars'].append(choice)
        
        selected = context.user_data['regression_ind_vars']
        all_cols = context.user_data.get('columns', [])
        
        markup = get_column_markup(all_cols, back_label='Back to Menu', extra_buttons=['Done Selecting'], selected_items=selected)
        
        await update.message.reply_text(
            f"Selected: {', '.join(selected)}\n\n"
            "Select more or tap 'Done Selecting':",
            reply_markup=markup
        )
        return ACTION

    # Handle correlation variable selection
    elif context.user_data.get('awaiting_corr_vars'):
        if choice == '◀️ Back to Menu':
            context.user_data['awaiting_corr_vars'] = False
            await show_action_menu(update)
            return ACTION
        
        if choice == 'Done Selecting':
            context.user_data['awaiting_corr_vars'] = False
            selected = context.user_data.get('selected_corr_vars', [])
            
            if len(selected) < 2:
                await update.message.reply_text("⚠️ Please select at least 2 variables.")
                return ACTION
            
            await update.message.reply_text("⚙️ Computing correlation matrix...")
            
            try:
                # df is pre-loaded at method start
                if df is None:
                    raise ValueError("Dataset not loaded.")
                result = Analyzer.get_correlation(df, columns=selected)
                
                if "error" in result:
                    await update.message.reply_text(f"Error: {result['error']}")
                else:
                    # Format as table
                    r_vals = result['r_values']
                    stars = result['stars']
                    p_vals = result['p_values']
                    
                    output = f"📊 **Correlation Matrix ({result['method']})**\n\n"
                    output += "```\n"
                    # Header
                    header = f"{'Var':<12}"
                    for col in r_vals.columns:
                        header += f" {col[:5]:>7}"
                    output += header + "\n"
                    output += "-" * len(header) + "\n"
                    
                    for row_name in r_vals.index:
                        row_str = f"{row_name[:12]:<12}"
                        for col_name in r_vals.columns:
                            r = r_vals.loc[row_name, col_name]
                            s = stars.loc[row_name, col_name]
                            val_str = f"{r:>.2f}{s}"
                            row_str += f" {val_str:>7}"
                        output += row_str + "\n"
                    
                    output += "```\n"
                    output += "* p < .05, ** p < .01, *** p < .001\n\n"
                    
                    await update.message.reply_text(output, parse_mode='Markdown')
                    
                    # Interpretation
                    interpreter = AIInterpreter()
                    ai_insight = await interpreter.interpret_results('correlation', {'matrix': r_vals.to_dict(), 'p_values': p_vals.to_dict()})
                    await update.message.reply_text(ai_insight)

            except Exception as e:
                await update.message.reply_text(f"⚠️ Error: {str(e)[:100]}")
            
            await show_action_menu(update)
            return ACTION

        # Add variable to list
        # VALIDATION: Ensure the choice is a valid column
        all_cols = context.user_data.get('num_cols', [])
        if choice not in all_cols and choice.replace('✅ ', '') not in all_cols:
            if choice != 'Done Selecting' and choice != '◀️ Back to Menu':
                await update.message.reply_text("⚠️ Invalid variable. Please select from the keyboard.")
                return ACTION

        # Clean selection (remove checkmark if present)
        clean_choice = choice.replace('✅ ', '')
        
        if 'selected_corr_vars' not in context.user_data:
            context.user_data['selected_corr_vars'] = []
            
        if clean_choice not in context.user_data['selected_corr_vars']:
            context.user_data['selected_corr_vars'].append(clean_choice)
        
        num_cols = context.user_data.get('num_cols', [])
        selected = context.user_data.get('selected_corr_vars', [])
        markup = get_column_markup(num_cols, extra_buttons=['Done Selecting'], back_label='◀️ Back to Menu', selected_items=selected)
        
        await update.message.reply_text(
            f"Selected: {', '.join(selected)}\n\n"
            "Select more variables or tap 'Done Selecting':",
            reply_markup=markup
        )
        return ACTION

    # The global load above handles df. If choice needs it, we check df.
    
    # Regression check fallthrough
    if choice == 'Regression':
        pass 

    # Handle crosstab type selection
    elif context.user_data.get('awaiting_crosstab_type'):
        context.user_data['awaiting_crosstab_type'] = False
        
        if choice == '◀️ Back to Menu':
            await show_action_menu(update)
            return ACTION
        
        all_cols = context.user_data.get('columns', [])
        col_rows = []
        for i in range(0, len(all_cols), 2):
            row = all_cols[i:i+2]
            col_rows.append(row)
        col_rows.append(['◀️ Back to Menu'])
        
        # Set crosstab mode
        if choice == '📊 Simple (1×1)':
            context.user_data['crosstab_mode'] = 'simple'
        elif choice == '📋 2×2 Table':
            context.user_data['crosstab_mode'] = '2x2'
        elif choice == '📈 2×N (Multiple)':
            context.user_data['crosstab_mode'] = '2xn'
        else:
            context.user_data['crosstab_mode'] = 'nxn'
        
        context.user_data['crosstab_row_vars'] = []
        context.user_data['crosstab_col_vars'] = []
        
        markup = get_column_markup(all_cols, extra_buttons=['✅ Done Selecting'])
        
        await update.message.reply_text(
            f"✅ Mode: **{choice}**\n\n"
            "Select the **ROW** variable(s):\n"
            "_For multiple, select one at a time then tap 'Done'_",
            parse_mode='Markdown',
            reply_markup=markup
        )
        context.user_data['awaiting_crosstab_row'] = True
        return ACTION


    # Handle TABULATION variable selection
    elif context.user_data.get('awaiting_tabulation_var'):
        if choice == '◀️ Back to Menu':
            context.user_data['awaiting_tabulation_var'] = False
            await show_action_menu(update)
            return ACTION

        if choice == 'Done Selecting':
            context.user_data['awaiting_tabulation_var'] = False
            vars = context.user_data.get('tabulation_vars', [])
            
            if not vars:
                await update.message.reply_text("⚠️ Please select at least one variable.")
                return ACTION
            
            # Process ALL selected variables
            await update.message.reply_text(f"⚙️ Generating Frequency Tables for {len(vars)} variables...")
            
            if df is None:
                 await update.message.reply_text("Dataset lost. Please reload.")
                 return ACTION

            for var in vars:
                try:
                    result = Analyzer.frequency_table(df, var)
                    if "error" in result:
                        await update.message.reply_text(f"⚠️ Error ({var}): {result['error']}")
                        continue
                        
                    table = result['table']
                    # Mobile-friendly format
                    output = f"📋 **Freq: {var}** (N={result['n_observations']})\n"
                    # output += f"Mode: {result['mode']}\n"
                    output += "```\n"
                    output += f"{'Category':<15} {'Freq':<5} {'%'}\n"
                    output += "-" * 30 + "\n"
                    
                    for idx in table.index[:15]: # Limit to top 15 for chat
                        count = table.loc[idx, 'Count']
                        pct = table.loc[idx, 'Percent']
                        cat_str = str(idx)[:15]
                        output += f"{cat_str:<15} {count:<5} {pct}\n"
                    output += "```\n"
                    
                    await update.message.reply_text(output, parse_mode='Markdown')

                    # Store for history
                    if 'analysis_history' not in context.user_data: context.user_data['analysis_history'] = []
                    context.user_data['analysis_history'].append({
                        'test': f'Frequency: {var}',
                        'vars': var,
                        'result': output,
                        'data': table.to_dict() # For manuscript table
                    })
                    
                except Exception as e:
                    await update.message.reply_text(f"⚠️ Error processing {var}: {e}")

            await show_action_menu(update, "✅ Tabulation Complete")
            return ACTION

        # Variable Selection Logic
        all_cols = context.user_data.get('columns', [])
        
        # Initialize list if needed
        if 'tabulation_vars' not in context.user_data:
            context.user_data['tabulation_vars'] = []
            
        clean_choice = choice.replace('✅ ', '')
        
        if clean_choice not in all_cols:
             if choice != 'Done Selecting':
                 await update.message.reply_text("⚠️ Invalid variable.")
                 return ACTION
        else:
             if clean_choice not in context.user_data['tabulation_vars']:
                 context.user_data['tabulation_vars'].append(clean_choice)
        
        selected = context.user_data['tabulation_vars']
        markup = get_column_markup(all_cols, extra_buttons=['Done Selecting'], selected_items=selected)
        
        await update.message.reply_text(
            f"Selected: {', '.join(selected)}\n\n"
            "Select more or tap 'Done':",
            reply_markup=markup
        )
        return ACTION

    # Handle tabulation visual suggestion
    elif context.user_data.get('awaiting_tabulation_visual'):
        context.user_data['awaiting_tabulation_visual'] = False
        var = context.user_data.get('last_tabulation_var')
        
        if choice == '⏭️ Skip - Back to Menu' or not var:
            await show_action_menu(update)
            return ACTION
        
        if choice in ['📊 Bar Chart', '🥧 Pie Chart', '📈 Line Chart', '📉 Histogram']:
             # Initialize Chart Config
             context.user_data['chart_type'] = choice
             context.user_data['chart_var'] = var
             context.user_data['chart_config'] = {
                 'title': f'{choice[2:]} of {var}',
                 'grid': True,
                 'legend': False,
                 'data_labels': False,
                 'xlabel': var,
                 'ylabel': 'Count'
             }
             
             # Call the new options handler
             return await chart_options_handler(update, context)
        
        await show_action_menu(update)
        return ACTION


    # Handle Frequency variable selection
    elif context.user_data.get('awaiting_freq_vars'):
        all_cols = context.user_data.get('columns', [])
        
        if choice == '◀️ Back to Menu':
             context.user_data['awaiting_freq_vars'] = False
             await show_action_menu(update)
             return ACTION

        if choice == '✅ Done Selecting':
             context.user_data['awaiting_freq_vars'] = False
             vars = context.user_data.get('freq_vars', [])
             if not vars:
                  await update.message.reply_text("⚠️ No variables selected.")
                  return ACTION
             
             await update.message.reply_text(f"📊 Analyzing frequencies for {len(vars)} variables...")
             
             for var in vars:
                  # Calculate Freqs
                  try:
                      counts = df[var].value_counts().sort_index()
                      pcts = df[var].value_counts(normalize=True).sort_index() * 100
                      res_df = pd.DataFrame({'Count': counts, 'Percent': pcts.round(2)})
                      res_df.index.name = var
                      
                      # Send table image
                      try:
                          from src.core.visualizer import Visualizer
                          img_path = Visualizer.create_stats_table_image(res_df, title=f"Frequency: {var}")
                          if img_path:
                               await update.message.reply_photo(photo=open(img_path, 'rb'))
                          else:
                               await update.message.reply_text(f"**{var}**\n{res_df.to_string()}", parse_mode='Markdown')
                      except:
                          await update.message.reply_text(f"**{var}**\n{res_df.to_string()}", parse_mode='Markdown')
                          
                      # Store in history
                      if 'analysis_history' not in context.user_data: context.user_data['analysis_history'] = []
                      context.user_data['analysis_history'].append({
                          'test': 'Frequency',
                          'vars': var,
                          'result': res_df.to_string(),
                          'data': res_df.reset_index().to_dict() # Serialize
                      })
                  except Exception as e:
                      await update.message.reply_text(f"⚠️ Error analyzing {var}: {str(e)}")

             await show_action_menu(update, "✅ Analysis Complete!")
             return ACTION
        
        # Selection Logic
        clean = choice.replace('✅ ', '')
        if clean not in all_cols:
             await update.message.reply_text("⚠️ Invalid variable. Please select from the keyboard.")
             return ACTION
             
        if 'freq_vars' not in context.user_data: context.user_data['freq_vars'] = []
        if clean not in context.user_data['freq_vars']:
             context.user_data['freq_vars'].append(clean)
             
        # Re-show keyboard
        selected = context.user_data['freq_vars']
        markup = get_column_markup(all_cols, extra_buttons=['✅ Done Selecting'], selected_items=selected)
        await update.message.reply_text(f"✅ Selected: {', '.join(selected)}\nSelect more or tap 'Done':", reply_markup=markup)
        return ACTION
        all_cols = context.user_data.get('columns', [])
        mode = context.user_data.get('crosstab_mode', 'simple')
        
        if choice == '◀️ Back to Menu':
            context.user_data['awaiting_crosstab_row'] = False
            await show_action_menu(update)
            return ACTION
        
        if choice == '✅ Done Selecting':
            context.user_data['awaiting_crosstab_row'] = False
            row_vars = context.user_data.get('crosstab_row_vars', [])
            
            if not row_vars:
                await update.message.reply_text("⚠️ Please select at least one row variable.")
                return ACTION
            
            # Move to column selection
            markup = get_column_markup(all_cols, extra_buttons=['✅ Done Selecting'])
            
            await update.message.reply_text(
                f"✅ Row variable(s): **{', '.join(row_vars)}**\n\n"
                "Now select **COLUMN** variable(s):\n"
                "_Tap 'Done' when finished_",
                parse_mode='Markdown',
                reply_markup=markup
            )
            context.user_data['awaiting_crosstab_col'] = True
            return ACTION
        
        # Add variable to list
        # VALIDATION
        all_cols = context.user_data.get('columns', [])
        clean_choice = choice.replace('✅ ', '')
        if clean_choice not in all_cols:
            if choice != '✅ Done Selecting' and choice != '◀️ Back to Menu':
                await update.message.reply_text("⚠️ Invalid variable. Please select from the keyboard.")
                return ACTION

        if 'crosstab_row_vars' not in context.user_data:
            context.user_data['crosstab_row_vars'] = []
        
        if clean_choice not in context.user_data['crosstab_row_vars']:
            context.user_data['crosstab_row_vars'].append(clean_choice)
        
        # For simple mode, move directly to column selection
        if mode == 'simple':
            context.user_data['awaiting_crosstab_row'] = False
            context.user_data['crosstab_row_var'] = choice
            context.user_data['crosstab_row_vars'] = [choice] # Keep sync
            
            markup = get_column_markup(all_cols)
            
            await update.message.reply_text(
                f"✅ Row: **{choice}**\n\n"
                "Now select the **COLUMN** variable:",
                parse_mode='Markdown',
                reply_markup=markup
            )
            context.user_data['awaiting_crosstab_col'] = True
            return ACTION
        
        # For multi-variable modes, allow more selections
        if 'crosstab_row_vars' not in context.user_data:
            context.user_data['crosstab_row_vars'] = []
            
        selected = context.user_data.get('crosstab_row_vars', [])
        markup = get_column_markup(all_cols, extra_buttons=['✅ Done Selecting'])
        
        await update.message.reply_text(
            f"✅ Selected: **{', '.join(selected)}**\n\n"
            "Select more or tap 'Done':",
            parse_mode='Markdown',
            reply_markup=markup
        )
        return ACTION

    # Handle crosstab column variable selection
    elif context.user_data.get('awaiting_crosstab_col'):
        context.user_data['awaiting_crosstab_col'] = False
        
        if choice == '◀️ Back to Menu':
            await show_action_menu(update)
            return ACTION
        
        if not context.user_data.get('crosstab_row_vars'):
            # Fallback if somehow empty
            context.user_data['crosstab_row_vars'] = [context.user_data.get('crosstab_row_var')]
            
        row_vars = [v for v in context.user_data.get('crosstab_row_vars', []) if v]
        row_display = row_vars[0] if row_vars else "None"
        
        col_var = choice
        context.user_data['crosstab_col_var'] = col_var
        context.user_data['crosstab_col_vars'] = [col_var]
        
        # Initialize display options (multi-select)
        context.user_data['crosstab_display'] = {'counts': True}  # Counts always on
        
        await update.message.reply_text(
            f"Row: {row_display} x Col: {col_var}\n\n"
            "**Select display options** (tap to toggle):\n"
            "[x] Counts (always included)\n"
            "[ ] Row %\n"
            "[ ] Column %\n"
            "[ ] Total %\n\n"
            "Tap options to select, then 'Generate Table':",
            parse_mode='Markdown',
            reply_markup=ReplyKeyboardMarkup([
                ['Toggle Row %', 'Toggle Column %'],
                ['Toggle Total %'],
                ['Generate Table', 'Back to Menu']
            ], one_time_keyboard=True)
        )
        context.user_data['awaiting_crosstab_options'] = True
        return ACTION

    # Handle crosstab display options toggle
    elif context.user_data.get('awaiting_crosstab_options'):
        display = context.user_data.get('crosstab_display', {'counts': True})
        
        if choice == 'Back to Menu':
            context.user_data['awaiting_crosstab_options'] = False
            await show_action_menu(update)
            return ACTION
        
        if 'Toggle' in choice:
            if 'Row' in choice:
                display['row_pct'] = not display.get('row_pct', False)
            elif 'Column' in choice:
                display['col_pct'] = not display.get('col_pct', False)
            elif 'Total' in choice:
                display['total_pct'] = not display.get('total_pct', False)
            
            context.user_data['crosstab_display'] = display
            
            # Show current selection
            row_vars = context.user_data.get('crosstab_row_vars', [])
            row_display = row_vars[0] if row_vars else "None"
            col_var = context.user_data.get('crosstab_col_var')
            
            status = (
                f"Row: {row_display} x Col: {col_var}\n\n"
                f"**Current Selection:**\n"
                f"[x] Counts\n"
                f"[{'x' if display.get('row_pct') else ' '}] Row %\n"
                f"[{'x' if display.get('col_pct') else ' '}] Column %\n"
                f"[{'x' if display.get('total_pct') else ' '}] Total %\n\n"
                "Tap to toggle more or 'Generate Table':"
            )
            
            await update.message.reply_text(
                status,
                parse_mode='Markdown',
                reply_markup=ReplyKeyboardMarkup([
                    ['Toggle Row %', 'Toggle Column %'],
                    ['Toggle Total %'],
                    ['Generate Table', 'Back to Menu']
                ], one_time_keyboard=True)
            )
            return ACTION
        
        if choice == 'Generate Table':
            context.user_data['awaiting_crosstab_options'] = False
            
            row_vars = context.user_data.get('crosstab_row_vars', [])
            col_var = context.user_data.get('crosstab_col_var')
            
            if not row_vars:
                # Fallback
                row_vars = [context.user_data.get('crosstab_row_var')]
            
            row_vars = [v for v in row_vars if v] # Filter None
            
            try:
                if df is None:
                    raise ValueError("Dataset not loaded.")
                await update.message.reply_text("⚙️ Creating crosstabulation...")
                
                all_outputs = []
                for row_var in row_vars:
                    # 1. Visual: Create Heatmap
                    heatmap_path = Visualizer.create_crosstab_heatmap(df, row_var, col_var)
                    
                    if heatmap_path:
                        await update.message.reply_photo(
                            photo=open(heatmap_path, 'rb'),
                            caption=f"📊 **Crosstab: {row_var} × {col_var}**"
                        )
                    else:
                        await update.message.reply_text(f"⚠️ Could not generate heatmap for {row_var}")

                    # 2. Data: Get detailed stats for Export
                    # We compute all percentages for the Excel export as requested
                    ct_counts = pd.crosstab(df[row_var], df[col_var], margins=True, margins_name='Total')
                    ct_row = pd.crosstab(df[row_var], df[col_var], normalize='index', margins=True, margins_name='Total').round(4) * 100
                    ct_col = pd.crosstab(df[row_var], df[col_var], normalize='columns', margins=True, margins_name='Total').round(4) * 100
                    
                    # Store detailed data for export logic
                    # We might need a combined dataframe for Excel, but for now let's store counts 
                    # and we can generate % in export_handler if needed, 
                    # OR we store a dict of DFs?
                    # The current export handler likely expects 'data' to be a single DF or Dict.
                    # We will store the Counts (Standard) but maybe trigger a special export mode?
                    # Let's start with Counts as primary, but user requested all % in export.
                    # We will assume export handler generates what it needs, or we provide a rich "result" string.
                    
                    # For consistency with current export handler:
                    result = Analyzer.crosstab(df, row_var, col_var, show_row_pct=True, show_col_pct=True, show_total_pct=True)
                    
                # (Loop continues to history storage below)

                # Store last result for export
                context.user_data['last_analysis'] = {
                    'type': 'crosstab',
                    'data': result['counts'],
                    'title': f'Crosstab_{row_var}_x_{col_var}'
                }
                
                # Store for history (use last result as proxy for overall table if multiple, or loop)
                # For safety, let's append EACH table if multiple were selected
                if 'analysis_history' not in context.user_data: context.user_data['analysis_history'] = []
                for row_var in row_vars:
                    # Re-run or store earlier? Re-running is safer if we want full data in dict
                    res_hist = Analyzer.crosstab(df, row_var, col_var)
                    context.user_data['analysis_history'].append({
                        'test': 'Crosstab',
                        'vars': f'{row_var} x {col_var}',
                        'result': Analyzer.format_crosstab_mobile(res_hist),
                        'data': res_hist['counts'].to_dict()
                    })

                await update.message.reply_text(
                    "✅ Analysis Complete!\n\n📥 Export options:",
                    reply_markup=ReplyKeyboardMarkup([
                        ['📤 Export to Excel', '📤 Export to CSV'],
                        ['◀️ Back to Menu']
                    ], one_time_keyboard=True, resize_keyboard=True)
                )
                return ACTION
                
            except Exception as e:
                logger.error(f"Crosstab generation failed: {e}", exc_info=True)
                await update.message.reply_text(f"⚠️ Error: {str(e)[:100]}")
            
            await show_action_menu(update)
            return ACTION
        
        return ACTION

    # Handle crosstab percentage selection (legacy - kept for compatibility)
    elif context.user_data.get('awaiting_crosstab_pct'):
        context.user_data['awaiting_crosstab_pct'] = False
        
        if choice == '◀️ Back to Menu':
            await show_action_menu(update)
            return ACTION
        
        row_var = context.user_data.get('crosstab_row_var')
        col_var = context.user_data.get('crosstab_col_var')
        
        show_row = 'Row' in choice
        show_col = 'Column' in choice
        show_total = 'Total' in choice
        
        try:
            if df is None:
                raise ValueError("Dataset not loaded.")
            await update.message.reply_text("Creating crosstabulation...")
            result = Analyzer.crosstab(df, row_var, col_var, 
                                       show_row_pct=show_row, 
                                       show_col_pct=show_col,
                                       show_total_pct=show_total)
            
            if "error" in result:
                await update.message.reply_text(f"Error: {result['error']}")
            else:
                output = Analyzer.format_crosstab_mobile(result)
                await update.message.reply_text(output)
                
                # Store for export
                context.user_data['last_analysis'] = {
                    'type': 'crosstab',
                    'data': result['counts'],
                    'title': f'Crosstab_{row_var}_x_{col_var}'
                }
                
                await update.message.reply_text(
                    "📥 Export options:",
                    reply_markup=ReplyKeyboardMarkup([
                        ['📤 Export to Excel', '📤 Export to CSV'],
                        ['◀️ Back to Menu']
                    ], one_time_keyboard=True, resize_keyboard=True)
                )
                return ACTION
        except Exception as e:
            await update.message.reply_text(f"Error: {str(e)[:100]}")
        
        await show_action_menu(update)
        return ACTION


    elif choice == '📝 Generate Report' or choice == 'Generate Report':

        # Check if user can access manuscript export
        user_id = update.message.from_user.id
        if not await check_feature(update, user_id, 'manuscript_export', 'Manuscript Export'):
            await show_action_menu(update)
            return ACTION
        
        # Show formatting options menu
        refs_count = len(context.user_data.get('references', []))
        analyses_count = len(context.user_data.get('analysis_history', []))
        
        await update.message.reply_text(
            f"📝 **Manuscript Settings**\n\n"
            f"📊 Analyses available: {analyses_count}\n"
            f"📚 References loaded: {refs_count}\n\n"
            "**Select Document Structure:**",
            parse_mode='Markdown',
            reply_markup=ReplyKeyboardMarkup([
                ['📄 IMRAD (Standard)', '📑 APA Research'],
                ['📖 Thesis Format', '📋 Report Format'],
                ['🔬 Journal Article', '⚙️ Custom'],
                ['◀️ Back to Menu']
            ], one_time_keyboard=True)
        )
        context.user_data['formatting_step'] = 'structure'
        return MANUSCRIPT_REVIEW


    elif choice == '🎨 Create Visuals' or choice == 'Create Visuals':
        num_cols = context.user_data.get('num_cols', [])
        all_cols = context.user_data.get('columns', [])
        
        await update.message.reply_text(
            "📊 **Create Visuals**\nSelect a chart type:",
            parse_mode='Markdown',
            reply_markup=ReplyKeyboardMarkup([
                ['📊 Bar Chart', '📈 Line Chart'],
                ['📉 Histogram', '🥧 Pie Chart'],
                ['🔵 Scatter Plot', '📦 Box Plot'],
                ['🕸️ Radar/Web Plot', '🔥 Heatmap'],
                ['🎻 Violin Plot', '🔗 Pair Plot'],
                ['◀️ Back to Menu']
            ], one_time_keyboard=True)
        )
        return VISUAL_SELECT

    elif choice == '💾 Save & Exit' or choice == 'Save & Exit':
        return await save_and_exit_handler(update, context)

    elif choice == '❌ Cancel' or choice == 'Cancel':
        await update.message.reply_text("👋 Goodbye! Use /start to begin again.", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END

    elif choice == '🧹 Clean & Sort' or choice == 'Clean & Sort Data':
        if df is not None:
            df = FileManager.clean_data(df)
            df = FileManager.sort_data(df, columns=[df.columns[0]])
            await update.message.reply_text("✅ Data cleaned and sorted by the first column.")
        else:
            await update.message.reply_text("⚠️ Dataset not available.")
        await show_action_menu(update)
        return ACTION

    elif choice == '📋 Show Data' or choice == 'Show Data Table':
        try:
            if df is None:
                raise ValueError("Dataset not loaded.")
            # Send text preview for easy copying
            preview = df.head(20).to_string()
            if len(preview) > 3800:
                preview = preview[:3800] + "\n...(truncated)"
            
            await update.message.reply_text(
                f"📋 Data Preview ({len(df)} rows, {len(df.columns)} columns)\n\n```\n{preview}\n```",
                parse_mode='Markdown'
            )
            
            # import os
            base_name = os.path.basename(file_path).replace('.', '_')
            excel_path = os.path.join(DATA_DIR, f"{base_name}_preview.xlsx")
            df.to_excel(excel_path, index=False)
            await update.message.reply_document(
                document=open(excel_path, 'rb'),
                caption="📊 Download Excel for full spreadsheet view"
            )
        except Exception as e:
            await update.message.reply_text(f"⚠️ Error: {str(e)[:100]}")
        
        await show_action_menu(update)
        return ACTION

    elif choice == '📚 Upload References' or choice == 'Upload References':
        from src.writing.citations import ReferenceParser
        
        # Show supported formats
        supported = ReferenceParser.get_supported_formats()
        
        await update.message.reply_text(
            f"📚 **Upload Reference File**\n\n"
            f"Send me a reference/bibliography file and I'll parse it for your manuscript.\n\n"
            f"**Supported Formats:**\n"
            f"• RIS (.ris) - EndNote, Zotero, Mendeley export\n"
            f"• BibTeX (.bib, .bibtex) - LaTeX bibliography\n"
            f"• EndNote XML (.xml)\n"
            f"• PubMed/MEDLINE (.nbib, .txt)\n"
            f"• CSV (.csv) - with title, author, year columns\n"
            f"• JSON (.json) - structured references\n"
            f"• ISI/Web of Science (.isi, .ciw)\n"
            f"• Plain text (.txt) - auto-detected\n\n"
            f"📎 *Upload your file now, or tap Back to return.*",
            parse_mode='Markdown',
            reply_markup=ReplyKeyboardMarkup([['◀️ Back to Menu']], one_time_keyboard=True)
        )
        context.user_data['awaiting_reference_file'] = True
        return ACTION

    # Fallback: show menu again
    await show_action_menu(update, "Please select an option from the menu:")
    return ACTION




async def manuscript_review_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Multi-step manuscript formatting wizard."""
    choice = update.message.text
    file_path = context.user_data.get('file_path')
    
    if not file_path:
        await update.message.reply_text("❌ No data file loaded. Please upload a file first.")
        return ACTION
    
    try:
        from src.core.file_manager import FileManager
        df, _ = FileManager.load_file(file_path)
    except Exception as e:
        logger.error(f"Error loading file in manuscript_review_handler: {e}")
        await update.message.reply_text("❌ Error loading data file. Please try uploading it again.")
        return ACTION

    formatting_step = context.user_data.get('formatting_step', 'structure')
    
    # Initialize settings if not exists
    if 'manuscript_settings' not in context.user_data:
        context.user_data['manuscript_settings'] = {
            'structure': 'imrad',
            'font': 'Times New Roman',
            'font_size': 12,
            'line_spacing': 'Double',
            'citation_style': 'apa7'
        }
    
    settings = context.user_data['manuscript_settings']
    
    # Navigation
    if choice == '◀️ Back to Menu' or choice == 'Back to Menu':
        await show_action_menu(update)
        return ACTION
    
    # Step 1: Structure Selection
    if formatting_step == 'structure':
        structure_map = {
            '📄 IMRAD (Standard)': 'imrad',
            '📑 APA Research': 'apa',
            '📖 Thesis Format': 'thesis',
            '📋 Report Format': 'report',
            '🔬 Journal Article': 'journal',
            '⚙️ Custom': 'custom'
        }
        
        if choice in structure_map:
            settings['structure'] = structure_map[choice]
            context.user_data['formatting_step'] = 'font'
            
            await update.message.reply_text(
                f"✅ Structure: **{choice}**\n\n"
                "**Select Font:**",
                parse_mode='Markdown',
                reply_markup=ReplyKeyboardMarkup([
                    ['Times New Roman', 'Arial'],
                    ['Calibri', 'Georgia'],
                    ['Cambria', 'Garamond'],
                    ['◀️ Back to Menu']
                ], one_time_keyboard=True)
            )
            return MANUSCRIPT_REVIEW
    
    # Step 2: Font Selection
    if formatting_step == 'font':
        valid_fonts = ['Times New Roman', 'Arial', 'Calibri', 'Georgia', 'Cambria', 'Garamond']
        if choice in valid_fonts:
            settings['font'] = choice
            context.user_data['formatting_step'] = 'spacing'
            
            await update.message.reply_text(
                f"✅ Font: **{choice}**\n\n"
                "**Select Line Spacing:**",
                parse_mode='Markdown',
                reply_markup=ReplyKeyboardMarkup([
                    ['Single (1.0)', '1.5 Spacing'],
                    ['Double (2.0)', 'Custom'],
                    ['◀️ Back to Menu']
                ], one_time_keyboard=True)
            )
            return MANUSCRIPT_REVIEW
    
    # Step 3: Spacing Selection
    if formatting_step == 'spacing':
        spacing_map = {
            'Single (1.0)': 'Single',
            '1.5 Spacing': '1.5',
            'Double (2.0)': 'Double',
            'Custom': 'Double'
        }
        if choice in spacing_map:
            settings['line_spacing'] = spacing_map[choice]
            context.user_data['formatting_step'] = 'citation'
            
            await update.message.reply_text(
                f"✅ Spacing: **{choice}**\n\n"
                "**Select Citation Style:**",
                parse_mode='Markdown',
                reply_markup=ReplyKeyboardMarkup([
                    ['APA 7th', 'MLA 9th'],
                    ['Harvard', 'Vancouver'],
                    ['Chicago', 'IEEE'],
                    ['◀️ Back to Menu']
                ], one_time_keyboard=True)
            )
            return MANUSCRIPT_REVIEW
    
    # Step 4: Citation Style Selection
    if formatting_step == 'citation':
        style_map = {
            'APA 7th': 'apa7',
            'MLA 9th': 'mla9',
            'Harvard': 'harvard',
            'Vancouver': 'vancouver',
            'Chicago': 'chicago',
            'IEEE': 'ieee'
        }
        if choice in style_map:
            settings['citation_style'] = style_map[choice]
            context.user_data['formatting_step'] = 'word_count'
            
            await update.message.reply_text(
                f"✅ Citation: **{choice}**\n\n"
                "**Target Word Count:**\n"
                "_Set your manuscript length target_",
                parse_mode='Markdown',
                reply_markup=ReplyKeyboardMarkup([
                    ['📝 Short (1500-2500)', '📄 Medium (3000-5000)'],
                    ['📖 Long (5000-8000)', '📑 Full (8000+)'],
                    ['✏️ Custom', '⏭️ No Limit'],
                    ['◀️ Back to Menu']
                ], one_time_keyboard=True)
            )
            return MANUSCRIPT_REVIEW
    
    # Step 5: Word Count Selection
    if formatting_step == 'word_count':
        word_count_map = {
            '📝 Short (1500-2500)': (1500, 2500),
            '📄 Medium (3000-5000)': (3000, 5000),
            '📖 Long (5000-8000)': (5000, 8000),
            '📑 Full (8000+)': (8000, 15000),
            '⏭️ No Limit': (0, 0)
        }
        
        if choice == '✏️ Custom':
            context.user_data['formatting_step'] = 'custom_word_count'
            await update.message.reply_text(
                "Enter your target word count:\n"
                "_Example: 4000 or 3000-5000 for range_",
                parse_mode='Markdown',
                reply_markup=ReplyKeyboardMarkup([['◀️ Back to Menu']], one_time_keyboard=True)
            )
            return MANUSCRIPT_REVIEW
        
        if choice in word_count_map:
            min_wc, max_wc = word_count_map[choice]
            settings['min_word_count'] = min_wc
            settings['max_word_count'] = max_wc
            context.user_data['formatting_step'] = 'confirm'
            
            # Show summary and confirm
            refs_count = len(context.user_data.get('references', []))
            analyses_count = len(context.user_data.get('analysis_history', []))
            
            wc_display = "No limit" if max_wc == 0 else f"{min_wc:,}-{max_wc:,}"
            
            await update.message.reply_text(
                f"📝 **Manuscript Settings Summary**\n\n"
                f"📄 Structure: {settings['structure'].upper()}\n"
                f"🔤 Font: {settings['font']} ({settings.get('font_size', 12)}pt)\n"
                f"📏 Spacing: {settings['line_spacing']}\n"
                f"📚 Citation: {settings['citation_style'].upper()}\n"
                f"📊 Word Count: {wc_display}\n"
                f"📈 Analyses: {analyses_count}\n"
                f"📖 References: {refs_count}\n\n"
                "Ready to generate?",
                parse_mode='Markdown',
                reply_markup=ReplyKeyboardMarkup([
                    ['✅ Generate Manuscript'],
                    ['📊 Export Excel Only'],
                    ['🔄 Change Settings', '◀️ Back to Menu']
                ], one_time_keyboard=True)
            )
            return MANUSCRIPT_REVIEW
    
    # Step 5b: Custom Word Count Entry
    if formatting_step == 'custom_word_count':
        try:
            if '-' in choice:
                parts = choice.split('-')
                min_wc = int(parts[0].strip())
                max_wc = int(parts[1].strip())
            else:
                target = int(choice.strip())
                min_wc = int(target * 0.9)
                max_wc = int(target * 1.1)
            
            settings['min_word_count'] = min_wc
            settings['max_word_count'] = max_wc
            context.user_data['formatting_step'] = 'confirm'
            
            refs_count = len(context.user_data.get('references', []))
            analyses_count = len(context.user_data.get('analysis_history', []))
            
            await update.message.reply_text(
                f"📝 **Manuscript Settings Summary**\n\n"
                f"📄 Structure: {settings['structure'].upper()}\n"
                f"🔤 Font: {settings['font']} ({settings.get('font_size', 12)}pt)\n"
                f"📏 Spacing: {settings['line_spacing']}\n"
                f"📚 Citation: {settings['citation_style'].upper()}\n"
                f"📊 Word Count: {min_wc:,}-{max_wc:,}\n"
                f"📈 Analyses: {analyses_count}\n"
                f"📖 References: {refs_count}\n\n"
                "Ready to generate?",
                parse_mode='Markdown',
                reply_markup=ReplyKeyboardMarkup([
                    ['✅ Generate Manuscript'],
                    ['📊 Export Excel Only'],
                    ['🔄 Change Settings', '◀️ Back to Menu']
                ], one_time_keyboard=True)
            )
            return MANUSCRIPT_REVIEW
        except ValueError:
            await update.message.reply_text(
                "⚠️ Invalid format. Please enter a number (e.g., 4000) or range (e.g., 3000-5000).",
                reply_markup=ReplyKeyboardMarkup([['◀️ Back to Menu']], one_time_keyboard=True)
            )
            return MANUSCRIPT_REVIEW


    
    # Step 5: Confirm and Generate
    if formatting_step == 'confirm':
        if choice == '✅ Generate Manuscript':
            try:
                await update.message.reply_text("⚙️ Generating manuscript with AI discussion... please wait.")
                
                from src.writing.generator import ManuscriptGenerator, ManuscriptSettings, FontFamily, DocumentStructure, LineSpacing
                from src.writing.citations import CitationStyle
                import os
                
                # Map settings to enums
                font_map = {
                    'Times New Roman': FontFamily.TIMES_NEW_ROMAN,
                    'Arial': FontFamily.ARIAL,
                    'Calibri': FontFamily.CALIBRI,
                    'Georgia': FontFamily.GEORGIA,
                    'Cambria': FontFamily.CAMBRIA,
                    'Garamond': FontFamily.GARAMOND
                }
                
                structure_map = {
                    'imrad': DocumentStructure.IMRAD,
                    'apa': DocumentStructure.APA_RESEARCH,
                    'thesis': DocumentStructure.THESIS,
                    'report': DocumentStructure.REPORT,
                    'journal': DocumentStructure.JOURNAL,
                    'custom': DocumentStructure.CUSTOM
                }
                
                spacing_map = {
                    'Single': LineSpacing.SINGLE,
                    '1.5': LineSpacing.ONE_HALF,
                    'Double': LineSpacing.DOUBLE
                }
                
                citation_map = {
                    'apa7': CitationStyle.APA7,
                    'mla9': CitationStyle.MLA9,
                    'harvard': CitationStyle.HARVARD,
                    'vancouver': CitationStyle.VANCOUVER,
                    'chicago': CitationStyle.CHICAGO,
                    'ieee': CitationStyle.IEEE
                }
                
                # Create settings
                ms = ManuscriptSettings(
                    font_family=font_map.get(settings['font'], FontFamily.TIMES_NEW_ROMAN),
                    font_size=settings.get('font_size', 12),
                    structure=structure_map.get(settings['structure'], DocumentStructure.IMRAD),
                    line_spacing=spacing_map.get(settings['line_spacing'], LineSpacing.DOUBLE),
                    citation_style=citation_map.get(settings['citation_style'], CitationStyle.APA7)
                )
                
                gen = ManuscriptGenerator(settings=ms)
                
                # Gather data
                analysis_history = context.user_data.get('analysis_history', [])
                references = context.user_data.get('references', [])
                
                # Build stats results with STRUCTURED TABLES
                stats_results = []
                
                # 1. Descriptive Stats Table
                try:
                    desc_df = Analyzer.get_descriptive_stats(df)
                    stats_results.append({
                        'type': 'table', 
                        'title': 'Table 1: Descriptive Statistics', 
                        'data': desc_df
                    })
                    # Keep legacy string for AI context
                    desc_res = desc_df.to_string()
                except:
                    desc_res = "Not available"
                    pass

                # 2. History Results
                for i, analysis in enumerate(analysis_history, 1):
                    try:
                        # Ensure analysis is a dict
                        if not isinstance(analysis, dict):
                            continue
                            
                        detailed_res = analysis.get('result', '')
                        test_name = analysis.get('test', f'Analysis {i}')
                        vars_str = analysis.get('vars', 'N/A')
                        
                        narrative = f"Analysis {i}: {test_name}\nVariables: {vars_str}\n{detailed_res}"
                        
                        # Try to get tabular data
                        data_content = analysis.get('data')
                        if isinstance(data_content, (dict, list)):
                             stats_results.append({
                                'type': 'table',
                                'title': f"Table {i+1}: {test_name} Results",
                                'data': data_content,
                                'narrative': narrative
                             })
                        else:
                            stats_results.append(narrative)
                    except Exception as loop_e:
                        print(f"Skipping analysis {i} due to error: {loop_e}")
                        continue
                
                # Gather visuals
                visuals_history = context.user_data.get('visuals_history', [])
                
                # Generate AI discussion
                try:
                    interpreter = AIInterpreter()
                    discussion = await interpreter.generate_discussion(
                        title=context.user_data.get('research_title', 'Statistical Analysis'),
                        objectives=context.user_data.get('research_objectives', 'N/A'),
                        questions=context.user_data.get('research_questions', 'N/A'),
                        hypotheses=context.user_data.get('research_hypothesis', 'N/A'),
                        analysis_history=analysis_history,
                        descriptive_stats=desc_res,
                        min_word_count=settings.get('min_word_count', 1500),
                        max_word_count=settings.get('max_word_count', 2500)
                    )
                except Exception as ai_e:
                    print(f"AI Discussion Error: {ai_e}")
                    discussion = "AI Discussion could not be generated."

                # Generate AI Citations if requested
                try:
                    ai_refs = await interpreter.generate_references(
                         title=context.user_data.get('research_title', ''),
                         objectives=context.user_data.get('research_objectives', '')
                    )
                    
                    # Convert to Reference objects (simplified)
                    from src.writing.citations import Reference
                    for ar in ai_refs:
                         references.append(Reference(
                             title=ar.get('title', ''),
                             authors=[ar.get('authors', '')],
                             year=ar.get('year', '2024'),
                             source=ar.get('source', '')
                         ))
                except Exception as ref_e:
                    print(f"AI Citation Error: {ref_e}")
                     
                # Add Chat Log as Appendix
                chat_log = context.user_data.get('chat_log', [])
                if chat_log:
                    formatted_chat = "AI Analysis Chat History:\n\n" + "\n\n".join(chat_log)
                    stats_results.append(formatted_chat)

                
                base_name = os.path.basename(file_path).replace('.', '_')
                out_path = os.path.join(DATA_DIR, f"{base_name}_manuscript.docx")
                
                result_path, word_count = gen.generate(
                    filename=out_path,
                    title=context.user_data.get('research_title', 'Statistical Analysis Report'),
                    authors=["QuantiProBot"],
                    abstract=f"This manuscript presents analysis of {len(df)} observations using {len(analysis_history)} statistical tests.",
                    content_sections={
                        "Research Objectives": context.user_data.get('research_objectives', 'N/A'),
                        "Research Questions": context.user_data.get('research_questions', 'N/A'),
                        "Hypotheses": context.user_data.get('research_hypothesis', 'N/A')
                    },
                    stats_results=stats_results,
                    discussion_text=discussion,
                    references=references,
                    images=visuals_history
                )
                
                await update.message.reply_document(
                    document=open(out_path, 'rb'),
                    caption=f"📄 Manuscript generated!\n📝 Word count: {word_count}\n📚 Format: {settings['structure'].upper()}"
                )
                await show_action_menu(update, "✅ Manuscript exported successfully!")
                
            except Exception as e:
                import traceback
                tb = traceback.format_exc()
                # Send first 1000 chars of traceback to user for debugging
                await update.message.reply_text(f"⚠️ **DEBUG ERROR INFO:**\n`{tb[:1000]}`", parse_mode='Markdown')
                await show_action_menu(update)
            
            context.user_data['formatting_step'] = None
            return ACTION
        
        elif choice == '📊 Export Excel Only':
            try:
                import os
                base_name = os.path.basename(file_path).replace('.', '_')
                out_path = os.path.join(DATA_DIR, f"{base_name}_data.xlsx")
                df.to_excel(out_path, index=False)
                await update.message.reply_document(document=open(out_path, 'rb'))
                await show_action_menu(update, "📊 Excel exported!")
            except Exception as e:
                await update.message.reply_text(f"⚠️ Error: {str(e)[:150]}")
                await show_action_menu(update)
            return ACTION
        
        elif choice == '🔄 Change Settings':
            context.user_data['formatting_step'] = 'structure'
            await update.message.reply_text(
                "**Select Document Structure:**",
                parse_mode='Markdown',
                reply_markup=ReplyKeyboardMarkup([
                    ['📄 IMRAD (Standard)', '📑 APA Research'],
                    ['📖 Thesis Format', '📋 Report Format'],
                    ['🔬 Journal Article', '⚙️ Custom'],
                    ['◀️ Back to Menu']
                ], one_time_keyboard=True)
            )
            return MANUSCRIPT_REVIEW
    
    # Default: restart wizard
    context.user_data['formatting_step'] = 'structure'
    await update.message.reply_text(
        "**Select Document Structure:**",
        parse_mode='Markdown',
        reply_markup=ReplyKeyboardMarkup([
            ['📄 IMRAD (Standard)', '📑 APA Research'],
            ['📖 Thesis Format', '📋 Report Format'],
            ['🔬 Journal Article', '⚙️ Custom'],
            ['◀️ Back to Menu']
        ], one_time_keyboard=True)
    )
    return MANUSCRIPT_REVIEW





async def visual_select_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Enhanced visual handler with full chart support and navigation."""
    choice = update.message.text
    file_path = context.user_data.get('file_path')
    df, _ = FileManager.load_file(file_path)
    num_cols = context.user_data.get('num_cols', [])
    all_cols = context.user_data.get('columns', [])
    
    # Navigation buttons
    nav_buttons = [['◀️ Back', '🏠 Main Menu', '💾 Save']]
    
    async def show_visual_menu(msg=""):
        # Get current settings for display
        config = context.user_data.get('visual_config', Visualizer.DEFAULT_CONFIG.copy())
        settings_summary = f"🎨 {config.get('palette', 'viridis')} | 📏 {config.get('size', 'medium')} | 🖌️ {config.get('style', 'whitegrid')}"
        
        text = f"{msg}\n\n**Current Settings:** {settings_summary}\n\n📊 **Create Visuals**\nSelect a chart type or change settings:" if msg else f"**Current Settings:** {settings_summary}\n\n📊 **Create Visuals**\nSelect a chart type or change settings:"
        
        await update.message.reply_text(
            text,
            parse_mode='Markdown',
            reply_markup=ReplyKeyboardMarkup([
                ['📊 Bar Chart', '📈 Line Chart'],
                ['📉 Histogram', '🥧 Pie Chart'],
                ['🔵 Scatter Plot', '📦 Box Plot'],
                ['🕸️ Radar/Web Plot', '🔥 Heatmap'],
                ['🎻 Violin Plot', '🔗 Pair Plot'],
                ['🎨 Chart Settings', '◀️ Back to Menu']
            ], one_time_keyboard=True)
        )
        return VISUAL_SELECT

    async def show_var_select(prompt, cols, include_back=True):
        keyboard = [[c] for c in cols[:10]]
        if include_back:
            keyboard.append(['◀️ Back'])
        await update.message.reply_text(
            prompt,
            parse_mode='Markdown',
            reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
        )
        return VISUAL_SELECT
    
    # Navigation handlers
    if choice == '◀️ Back to Menu' or choice == '🏠 Main Menu':
        context.user_data['visual_type'] = None
        context.user_data['visual_step'] = None
        # Clean temp states
        keys_to_remove = ['visual_setting_mode']
        for k in keys_to_remove:
            if k in context.user_data: del context.user_data[k]
        await show_action_menu(update)
        return ACTION
    
    if choice == '◀️ Back':
        context.user_data['visual_step'] = None
        context.user_data['visual_setting_mode'] = None
        return await show_visual_menu()
    
    if choice == '💾 Save':
        return await save_and_exit_handler(update, context)

    # --- SETTINGS MENU HANDLERS ---
    if choice == '🎨 Chart Settings':
        await update.message.reply_text(
            "🎨 **Visual Output Settings**\n\nWhat would you like to customize?",
            parse_mode='Markdown',
            reply_markup=ReplyKeyboardMarkup([
                ['🎨 Color Palette', '📏 Chart Size'],
                ['🖌️ Plot Style', '◀️ Back']
            ], one_time_keyboard=True)
        )
        context.user_data['visual_setting_mode'] = 'menu'
        return VISUAL_SELECT

    # Handle Sub-menus or values
    if context.user_data.get('visual_setting_mode') == 'menu':
        if choice == '🎨 Color Palette':
            context.user_data['visual_setting_mode'] = 'palette'
            await update.message.reply_text(
                "🎨 **Select Color Palette:**",
                reply_markup=ReplyKeyboardMarkup([
                    ['Viridis', 'Plasma', 'Inferno', 'Magma'],
                    ['Deep', 'Muted', 'Pastel', 'Bright'],
                    ['Set1', 'Set2', 'Set3', 'Paired'],
                    ['◀️ Back']
                ], one_time_keyboard=True)
            )
            return VISUAL_SELECT
            
        elif choice == '📏 Chart Size':
            context.user_data['visual_setting_mode'] = 'size'
            await update.message.reply_text(
                "📏 **Select Chart Size:**",
                reply_markup=ReplyKeyboardMarkup([
                    ['Small', 'Medium', 'Large'],
                    ['◀️ Back']
                ], one_time_keyboard=True)
            )
            return VISUAL_SELECT

        elif choice == '🖌️ Plot Style':
            context.user_data['visual_setting_mode'] = 'style'
            await update.message.reply_text(
                "🖌️ **Select Plot Style:**",
                reply_markup=ReplyKeyboardMarkup([
                    ['Whitegrid', 'Darkgrid'],
                    ['White', 'Dark', 'Ticks'],
                    ['◀️ Back']
                ], one_time_keyboard=True)
            )
            return VISUAL_SELECT
    
    # Handle Setting Value Selection
    setting_mode = context.user_data.get('visual_setting_mode')
    
    if setting_mode in ['palette', 'size', 'style']:
        if choice == '◀️ Back':
             # Return to settings menu
             context.user_data['visual_setting_mode'] = 'menu'
             await update.message.reply_text(
                "🎨 **Visual Output Settings**\nTo apply changes, tap Back again.",
                reply_markup=ReplyKeyboardMarkup([
                    ['🎨 Color Palette', '📏 Chart Size'],
                    ['🖌️ Plot Style', '◀️ Back']
                ], one_time_keyboard=True)
             )
             return VISUAL_SELECT
             
        # Save preference
        if 'visual_config' not in context.user_data:
            context.user_data['visual_config'] = Visualizer.DEFAULT_CONFIG.copy()
        
        if setting_mode == 'palette':
            context.user_data['visual_config']['palette'] = choice.lower()
            msg = f"✅ Palette set to **{choice}**"
        elif setting_mode == 'size':
            context.user_data['visual_config']['size'] = choice.lower()
            msg = f"✅ Size set to **{choice}**"
        elif setting_mode == 'style':
            context.user_data['visual_config']['style'] = choice.lower()
            msg = f"✅ Style set to **{choice}**"
            
        # Return to main visual menu to confirm
        context.user_data['visual_setting_mode'] = None
        return await show_visual_menu(msg)


    # --- CHART GENERATION HANDLERS (Updated with Config) ---
    # Get config for all calls
    v_config = context.user_data.get('visual_config', Visualizer.DEFAULT_CONFIG.copy())

    if choice == '📊 Bar Chart':
        context.user_data['visual_type'] = 'bar_chart'
        return await show_var_select("📊 Select the **category variable** (X-axis):", all_cols)
    
    elif choice == '📈 Line Chart':
        context.user_data['visual_type'] = 'line_chart'
        context.user_data['visual_step'] = 1
        return await show_var_select("📈 Select the **X-axis variable** (e.g., time, sequence):", all_cols)
    
    elif choice == '📉 Histogram':
        context.user_data['visual_type'] = 'histogram'
        return await show_var_select("📉 Select a **numeric variable**:", num_cols)
    
    elif choice == '🥧 Pie Chart':
        context.user_data['visual_type'] = 'pie_chart'
        return await show_var_select("🥧 Select a **categorical variable**:", all_cols)
    
    elif choice == '🔵 Scatter Plot':
        context.user_data['visual_type'] = 'scatter_plot'
        context.user_data['visual_step'] = 1
        return await show_var_select("🔵 Select the **X variable**:", num_cols)
    
    elif choice == '📦 Box Plot':
        context.user_data['visual_type'] = 'box_plot'
        context.user_data['visual_step'] = 1
        return await show_var_select("📦 Select the **grouping variable** (X):", all_cols)
    
    elif choice == '🕸️ Radar/Web Plot':
        await update.message.reply_text("⚙️ **Generating Radar Chart...**\nUsing all numeric variables.")
        if df is not None and len(num_cols) >= 3:
            path = Visualizer.create_radar_chart(df, num_cols[:8], config=v_config)
            if path:
                await update.message.reply_photo(photo=open(path, 'rb'), caption=f"🕸️ Radar Chart ({v_config.get('palette')})")
                if 'visuals_history' not in context.user_data: context.user_data['visuals_history'] = []
                context.user_data['visuals_history'].append(path)
            else:
                await update.message.reply_text("❌ Could not generate radar chart (need at least 3 numeric variables).")
        else:
            await update.message.reply_text("❌ Need at least 3 numeric variables for radar chart.")
        return await show_visual_menu()
    
    elif choice == '🔥 Heatmap':
        await update.message.reply_text("⚙️ **Generating Correlation Heatmap...**")
        if df is not None:
             path = Visualizer.create_correlation_heatmap(df, config=v_config)
        if path:
            await update.message.reply_photo(photo=open(path, 'rb'), caption="🔥 Correlation Heatmap")
            if 'visuals_history' not in context.user_data: context.user_data['visuals_history'] = []
            context.user_data['visuals_history'].append(path)
        else:
            await update.message.reply_text("❌ Could not generate heatmap.")
        return await show_visual_menu()
    
    elif choice == '🎻 Violin Plot':
        context.user_data['visual_type'] = 'violin_plot'
        context.user_data['visual_step'] = 1
        return await show_var_select("🎻 Select the **grouping variable** (X):", all_cols)
    
    elif choice == '🔗 Pair Plot':
        await update.message.reply_text("⚙️ **Generating Pair Plot...**\nThis may take a moment.")
        if df is not None and len(num_cols) >= 2:
            path = Visualizer.create_pair_plot(df, num_cols[:5])
            if path:
                await update.message.reply_photo(photo=open(path, 'rb'), caption="🔗 Pair Plot (Scatter Matrix)")
                if 'visuals_history' not in context.user_data: context.user_data['visuals_history'] = []
                context.user_data['visuals_history'].append(path)
            else:
                await update.message.reply_text("❌ Could not generate pair plot.")
        else:
            await update.message.reply_text("❌ Need at least 2 numeric variables for pair plot.")
        return await show_visual_menu()
    
    # Variable selection handlers
    vtype = context.user_data.get('visual_type')
    vstep = context.user_data.get('visual_step', 0)
    
    if vtype and df is not None and choice in df.columns:
        # Single variable charts
        if vtype == 'histogram':
            await update.message.reply_text("⚙️ **Generating Histogram...**")
            path = Visualizer.create_histogram(df, choice, config=v_config)
            if path:
                await update.message.reply_photo(photo=open(path, 'rb'), caption=f"📉 Histogram: {choice}")
                if 'visuals_history' not in context.user_data: context.user_data['visuals_history'] = []
                context.user_data['visuals_history'].append(path)
            context.user_data['visual_type'] = None
            return await show_visual_menu("✅ Histogram generated!")
        
        elif vtype == 'pie_chart':
            await update.message.reply_text("⚙️ **Generating Pie Chart...**")
            path = Visualizer.create_pie_chart(df, choice, config=v_config)
            if path:
                await update.message.reply_photo(photo=open(path, 'rb'), caption=f"🥧 Pie Chart: {choice}")
                if 'visuals_history' not in context.user_data: context.user_data['visuals_history'] = []
                context.user_data['visuals_history'].append(path)
            context.user_data['visual_type'] = None
            return await show_visual_menu("✅ Pie chart generated!")
        
        elif vtype == 'bar_chart':
            await update.message.reply_text("⚙️ **Generating Bar Chart...**")
            path = Visualizer.create_bar_chart(df, choice, config=v_config)
            if path:
                await update.message.reply_photo(photo=open(path, 'rb'), caption=f"📊 Bar Chart: {choice}")
                if 'visuals_history' not in context.user_data: context.user_data['visuals_history'] = []
                context.user_data['visuals_history'].append(path)
            context.user_data['visual_type'] = None
            return await show_visual_menu("✅ Bar chart generated!")
        
        # Two-variable charts - Step 1
        elif vstep == 1:
            context.user_data['visual_var1'] = choice
            context.user_data['visual_step'] = 2
            return await show_var_select(f"Now select the **second variable** (Y):", num_cols if vtype != 'box_plot' else num_cols)
        
        # Two-variable charts - Step 2
        elif vstep == 2:
            var1 = context.user_data.get('visual_var1')
            await update.message.reply_text(f"⚙️ **Generating {vtype.replace('_', ' ').title()}...**")
            
            if vtype == 'scatter_plot':
                path = Visualizer.create_scatterplot(df, var1, choice, config=v_config)
                caption = f"🔵 Scatter: {var1} vs {choice}"
            elif vtype == 'box_plot':
                path = Visualizer.create_boxplot(df, var1, choice, config=v_config)
                caption = f"📦 Box Plot: {choice} by {var1}"
            elif vtype == 'line_chart':
                path = Visualizer.create_line_chart(df, var1, choice, config=v_config)
                caption = f"📈 Line: {choice} over {var1}"
            elif vtype == 'violin_plot':
                path = Visualizer.create_violin_plot(df, var1, choice, config=v_config)
                caption = f"🎻 Violin: {choice} by {var1}"
            else:
                path = None
                caption = ""
            
            if path:
                await update.message.reply_photo(photo=open(path, 'rb'), caption=caption)
                if 'visuals_history' not in context.user_data: context.user_data['visuals_history'] = []
                context.user_data['visuals_history'].append(path)
            else:
                await update.message.reply_text("❌ Could not generate chart.")
            
            context.user_data['visual_type'] = None
            context.user_data['visual_step'] = None
            return await show_visual_menu("✅ Chart generated!")
    
    # Default: show visual menu
    return await show_visual_menu()



async def plans_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    db = DatabaseManager()
    user = db.get_user(user_id)
    
    if not user:
        await update.message.reply_text("Please use /start to register first.")
        return
    
    currency = user.local_currency or "NGN"
    rate = {"NGN": 1600, "GHS": 15, "KES": 155, "ZAR": 19, "USD": 1}.get(currency, 1600)
    
    msg = "**QuantiProBot Plans**\n\n"
    msg += "_Select a plan to subscribe_\n\n"
    
    # Plan details
    plans_info = [
        ("Free", 0, "5 analyses, 2 AI/day, 150 rows"),
        ("Student", 9.99, "500 rows, 10 AI/day, IMRAD export"),
        ("Researcher", 24.99, "5000 rows, 50 AI/day, All exports"),
        ("Institution", 149.00, "20 seats, Priority support, Team Dashboard"),
    ]
    
    for name, price, features in plans_info:
        if price == 0:
            msg += f"**{name}** - FREE\n  {features}\n\n"
        else:
            yearly = round(price * 12 * 0.75, 2)
            local_mo = int(price * rate)
            local_yr = int(yearly * rate)
            msg += f"**{name}** - ${price}/mo | ${yearly}/yr\n"
            msg += f"  Local: {local_mo:,}/mo | {local_yr:,}/yr {currency}\n"
            msg += f"  {features}\n\n"
    
    msg += "_Save 25% with yearly billing!_"
    
    # Plan selection buttons
    keyboard = [
        [InlineKeyboardButton("Student $9.99/mo", callback_data="select_Student_monthly")],
        [InlineKeyboardButton("Researcher $24.99/mo", callback_data="select_Researcher_monthly")],
        [InlineKeyboardButton("Institution $149/mo", callback_data="select_Institution_monthly")],
        [InlineKeyboardButton("--- Yearly (25% off) ---", callback_data="show_yearly")],
        [InlineKeyboardButton("Student $89.99/yr", callback_data="select_Student_yearly")],
        [InlineKeyboardButton("Researcher $224.99/yr", callback_data="select_Researcher_yearly")],
        [InlineKeyboardButton("Institution $1341/yr", callback_data="select_Institution_yearly")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
        
    await update.message.reply_text(msg, parse_mode='Markdown', reply_markup=reply_markup)


async def payment_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle payment-related callbacks."""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    # Plan selection
    if data.startswith("select_"):
        parts = data.replace("select_", "").split("_")
        plan_name = parts[0]
        period = parts[1] if len(parts) > 1 else "monthly"
        
        context.user_data['selected_plan'] = plan_name
        context.user_data['selected_period'] = period
        
        # Calculate price
        prices = {"Student": 9.99, "Researcher": 24.99, "Institution": 149.00}
        price = prices.get(plan_name, 0)
        if period == "yearly":
            price = round(price * 12 * 0.75, 2)
        
        keyboard = [
            [InlineKeyboardButton("Pay with Paystack", callback_data=f"pay_paystack_{plan_name}_{period}")],
            [InlineKeyboardButton("Pay with Telegram Stars", callback_data=f"pay_stars_{plan_name}_{period}")],
            [InlineKeyboardButton("Back to Plans", callback_data="back_to_plans")]
        ]
        
        await query.edit_message_text(
            f"**Selected: {plan_name} ({period.title()})**\n\n"
            f"Price: ${price}\n\n"
            "Choose payment method:",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    # Paystack payment
    elif data.startswith("pay_paystack_"):
        parts = data.replace("pay_paystack_", "").split("_")
        plan_name = parts[0]
        period = parts[1] if len(parts) > 1 else "monthly"
        
        from src.bot.payments import initiate_paystack_payment
        
        result = await initiate_paystack_payment(update, context, plan_name, period)
        
        if result.startswith("error:"):
            error = result.replace("error:", "")
            if error == "no_email":
                await query.edit_message_text("Please update your profile with an email address first. Use /profile")
            else:
                await query.edit_message_text(f"Payment error: {error}")
        else:
            keyboard = [[InlineKeyboardButton("Complete Payment", url=result)]]
            await query.edit_message_text(
                f"**Payment Initiated**\n\n"
                f"Plan: {plan_name} ({period})\n\n"
                "Click below to complete payment:",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
    
    # Telegram Stars payment
    elif data.startswith("pay_stars_"):
        parts = data.replace("pay_stars_", "").split("_")
        plan_name = parts[0]
        period = parts[1] if len(parts) > 1 else "monthly"
        
        from src.bot.payments import TelegramStarsPayment
        
        await query.edit_message_text("Preparing Telegram Stars invoice...")
        
        success = await TelegramStarsPayment.send_invoice(update, context, plan_name, period)
        
        if not success:
            await query.message.reply_text("Failed to create invoice. Please try again.")
    
    # Back to plans
    elif data == "back_to_plans" or data == "show_yearly":
        await query.message.reply_text("Use /plans to see available plans.")


async def pre_checkout_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle pre-checkout query for Telegram Stars."""
    from src.bot.payments import TelegramStarsPayment
    await TelegramStarsPayment.handle_pre_checkout(update, context)


async def successful_payment_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle successful Telegram Stars payment."""
    from src.bot.payments import TelegramStarsPayment, activate_subscription
    
    result = await TelegramStarsPayment.handle_successful_payment(update, context)
    
    if result["success"]:
        # Activate subscription
        activated = await activate_subscription(
            result["user_id"],
            result["plan"],
            result["period"]
        )
        
        if activated:
            await update.message.reply_text(
                f"Payment successful!\n\n"
                f"Plan: {result['plan']} ({result['period']})\n"
                f"Stars paid: {result['stars_paid']}\n\n"
                "Your subscription is now active!"
            )
        else:
            await update.message.reply_text(
                "Payment received but activation failed. Please contact support."
            )
    else:
        await update.message.reply_text("Payment processing error. Please contact support.")


async def myplan_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    db = DatabaseManager()
    user = db.get_user(user_id)
    
    if not user:
        await update.message.reply_text("Please use /start to register first.")
        return

    expiry_str = user.subscription_expiry.strftime("%Y-%m-%d") if user.subscription_expiry else "N/A"
    
    msg = (
        f"📋 **Your Subscription Status**\n\n"
        f"**Plan**: {user.plan.name}\n"
        f"**Row Limit**: {user.plan.row_limit}\n"
        f"**Status**: {'Active' if not user.subscription_expiry or user.subscription_expiry > datetime.utcnow() else 'Expired'}\n"
        f"**Due Date**: {expiry_str}\n\n"
        "To upgrade, use /plans"
    )
    await update.message.reply_text(msg, parse_mode='Markdown')

async def profile_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    db = DatabaseManager()
    user = db.get_user(user_id)
    
    if not user:
        await update.message.reply_text("Please use /start to register first.")
        return
    
    msg = (
        f"👤 **User Profile**\n\n"
        f"**Name**: {user.full_name}\n"
        f"**Email**: {user.email}\n"
        f"**Phone**: {user.phone}\n"
        f"**Country**: {user.country}\n"
        f"**Member Since**: {user.signup_date.strftime('%Y-%m-%d')}\n"
        f"**Plan**: {user.plan.name}"
    )

    # Show Institutional Admin info
    if user.plan.name == "Institution" and not user.institution_admin_id:
        if not user.invite_code:
            db.generate_invite_code(user_id)
            user = db.get_user(user_id)
        msg += f"\n\n🔑 **Institution Invite Code**: `{user.invite_code}`\n"
        msg += f"Share this code with up to 20 members to join your institution."
    elif user.institution_admin_id:
        admin = db.get_user(user.institution_admin_id)
        msg += f"\n\n🏢 **Institution Lead**: {admin.full_name if admin else 'N/A'}"

    keyboard = [
        [InlineKeyboardButton("✏️ Edit Profile", callback_data="profile_edit")],
        [InlineKeyboardButton("🗑️ Delete Account", callback_data="profile_delete")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(msg, parse_mode='Markdown', reply_markup=reply_markup)

async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comprehensive help guide for QuantiProBot."""
    help_text = (
        "📖 **QuantiProBot User Guide**\n\n"
        "QuantiProBot is your advanced AI-powered data analyst. Here's how to use it:\n\n"
        "🚀 **Getting Started**\n"
        "1. Send /start to begin.\n"
        "2. Upload your dataset (.csv, .xlsx, .sav, .dta).\n"
        "3. Select what you'd like to do from the menu.\n\n"
        "📋 **Core Commands**\n"
        "• /start - Main menu / Upload data\n"
        "• /profile - View and edit your info\n"
        "• /plans - Upgrade your subscription\n"
        "• /history - View/Continue past projects\n"
        "• /help - Show this guide\n"
        "• /cancel - Abort current action\n\n"
        "🏢 **Institutional Plans**\n"
        "If you are part of a team, use:\n"
        "• `/join CODE` - Join using an invite code\n\n"
        "📊 **Analytical Features**\n"
        "• **AI Chat**: Ask questions about your data in plain English.\n"
        "• **Regression**: Linear, Logistic, and Multiple regression analysis.\n"
        "• **Correlation**: Multi-select variables to see relation matrix with p-values.\n"
        "• **Generate Report**: Create a full academic manuscript (Word doc).\n\n"
        "Need more help? Contact @QuantiProSupport"
    )
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def ping_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Simple connectivity test."""
    await update.message.reply_text("🏓 **Pong!** Bot is online and responsive.", parse_mode='Markdown')

async def join_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle joining an institution via invite code."""
    user_id = update.message.from_user.id
    if not context.args:
        await update.message.reply_text("❌ Please provide the invite code. Usage: `/join CODE`", parse_mode='Markdown')
        return

    invite_code = context.args[0].upper()
    db = DatabaseManager()
    result = db.join_institution(user_id, invite_code)

    if "success" in result:
        await update.message.reply_text(f"✅ **Success!** {result['success']}\n\nYou now have Institutional access.", parse_mode='Markdown')
    else:
        await update.message.reply_text(f"❌ **Error:** {result['error']}", parse_mode='Markdown')

async def profile_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "profile_delete":
        keyboard = [
            [InlineKeyboardButton("Yes, Delete My Account", callback_data="confirm_delete")],
            [InlineKeyboardButton("No, Keep It", callback_data="cancel_delete")]
        ]
        await query.edit_message_text(
            "WARNING\n\nAre you sure you want to delete your account? This will erase all your research history and subscription data.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    elif query.data == "confirm_delete":
        db = DatabaseManager()
        db.delete_user(query.from_user.id)
        await query.edit_message_text("Your account has been deleted. Send /start if you wish to register again.")
    elif query.data == "cancel_delete":
        await query.edit_message_text("Account deletion cancelled.")
    elif query.data == "profile_edit":
        keyboard = [
            [InlineKeyboardButton("Edit Name", callback_data="edit_name")],
            [InlineKeyboardButton("Edit Email", callback_data="edit_email")],
            [InlineKeyboardButton("Edit Phone", callback_data="edit_phone")],
            [InlineKeyboardButton("Edit Country", callback_data="edit_country")],
            [InlineKeyboardButton("Cancel", callback_data="edit_cancel")]
        ]
        await query.edit_message_text(
            "**Edit Profile**\n\nSelect which field to update:",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    elif query.data.startswith("edit_"):
        field = query.data.replace("edit_", "")
        if field == "cancel":
            await query.edit_message_text("Profile edit cancelled. Use /profile to view your profile.")
            return
        
        context.user_data['editing_field'] = field
        field_labels = {
            'name': 'Full Name',
            'email': 'Email Address',
            'phone': 'Phone Number',
            'country': 'Country'
        }
        
        await query.edit_message_text(
            f"**Edit {field_labels.get(field, field.title())}**\n\n"
            f"Please send your new {field_labels.get(field, field)} as a message.\n"
            f"(Or send 'cancel' to abort)",
            parse_mode='Markdown'
        )
    elif "pay_" in query.data or "billing_" in query.data:
        if "billing_monthly" in query.data:
            await query.edit_message_text("Selected: Monthly billing. Use the payment buttons below to subscribe.", parse_mode='Markdown')
        elif "billing_yearly" in query.data:
            await query.edit_message_text("Selected: Yearly billing (25% off). Use the payment buttons below to subscribe.", parse_mode='Markdown')
        else:
            method = "Paystack" if "paystack" in query.data else "Telegram Stars"
            await query.edit_message_text(f"Redirecting to {method}...\n\n(Integration in progress - this will open your payment link).")


async def signup_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await SignupManager.start_signup(update, context)


async def history_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user's saved analysis tasks."""
    user_id = update.message.from_user.id
    db = DatabaseManager()
    user = db.get_user(user_id)
    
    if not user:
        await update.message.reply_text("Please use /start to register first.")
        return
    
    tasks = db.get_user_tasks(user_id)
    
    if not tasks:
        await update.message.reply_text("📭 No saved tasks found.\n\nStart a new analysis with /start!")
        return
    
    msg = "📚 **Your Analysis History**\n\n"
    keyboard = []
    for t in tasks:
        status_icon = "✅" if t['status'] == 'completed' else "💾" if t['status'] == 'saved' else "⏳"
        msg += f"{status_icon} **{t['title']}**\n   Created: {t['created']}\n\n"
        keyboard.append([InlineKeyboardButton(f"Continue: {t['title'][:20]}...", callback_data=f"load_task_{t['id']}")])
    
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="history_back")])
    
    await update.message.reply_text(
        msg,
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def admin_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Super Admin Console for managing users."""
    user_id = update.message.from_user.id
    db = DatabaseManager()
    user = db.get_user(user_id)
    
    if not user or not user.is_admin:
        await update.message.reply_text("🚫 Access Denied. Admin privileges required.")
        return
    
    # Show admin menu
    await update.message.reply_text(
        "🛡️ **SUPER ADMIN CONSOLE**\n\n"
        "Choose an action:",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("👥 View All Users", callback_data="admin_users")],
            [InlineKeyboardButton("📊 System Stats", callback_data="admin_stats")],
            [InlineKeyboardButton("✅ Verify User", callback_data="admin_verify")],
            [InlineKeyboardButton("⬆️ Upgrade User Plan", callback_data="admin_upgrade")],
            [InlineKeyboardButton("🔙 Close", callback_data="admin_close")]
        ])
    )


async def admin_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle admin panel callbacks."""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    db = DatabaseManager()
    user = db.get_user(user_id)
    
    if not user or not user.is_admin:
        await query.edit_message_text("🚫 Access Denied.")
        return
    
    if query.data == "admin_users":
        users = db.get_all_users()
        msg = "👥 **All Users**\n\n"
        for u in users[:15]:  # Limit to 15 for readability
            verified = "✅" if u['verified'] else "❌"
            admin = "👑" if u['admin'] else ""
            msg += (
                f"━━━━━━━━━━━━━━━━\n"
                f"👤 **{u['name']}** {admin}\n"
                f"🆔 TG ID: `{u['id']}`\n"
                f"📧 {u['email']}\n"
                f"📱 {u['phone']}\n"
                f"🌍 {u['country']}\n"
                f"💳 Plan: **{u['plan']}**\n"
                f"📅 Expires: {u['expiry']}\n"
                f"🗓️ Joined: {u['signup_date']} {verified}\n"
            )
        msg += f"\n━━━━━━━━━━━━━━━━\n📊 Total: {len(users)} users"
        await query.edit_message_text(msg, parse_mode='Markdown')
    
    elif query.data == "admin_stats":
        users = db.get_all_users()
        total = len(users)
        verified = sum(1 for u in users if u['verified'])
        admins = sum(1 for u in users if u['admin'])
        await query.edit_message_text(
            f"📊 **System Statistics**\n\n"
            f"Total Users: {total}\n"
            f"Verified: {verified}\n"
            f"Admins: {admins}",
            parse_mode='Markdown'
        )
    
    elif query.data == "admin_verify":
        await query.edit_message_text(
            "Enter the Telegram ID of the user to verify:\n"
            "(Use /admin to return to menu)"
        )
        context.user_data['admin_action'] = 'verify'
    
    elif query.data == "admin_upgrade":
        await query.edit_message_text(
            "Enter: `USER_ID PLAN_NAME`\n"
            "Example: `123456789 Professional`\n"
            "(Use /admin to return to menu)",
            parse_mode='Markdown'
        )
        context.user_data['admin_action'] = 'upgrade'
    
    elif query.data == "admin_close":
        await query.edit_message_text("Admin console closed.")
    
    elif query.data.startswith("load_task_"):
        task_id = int(query.data.replace("load_task_", ""))
        task = db.get_task(task_id)
        if task:
            # Restore context
            context.user_data.update(task['context'])
            context.user_data['file_path'] = task['file_path']
            context.user_data['loaded_task_id'] = task_id
            
            # Restore references if they were saved as dicts
            if 'references' in task['context']:
                from src.writing.citations import Reference
                refs = []
                for r in task['context'].get('references', []):
                    if isinstance(r, dict):
                        refs.append(Reference(
                            title=r.get('title', ''),
                            authors=r.get('authors', []),
                            year=r.get('year', ''),
                            source=r.get('source', ''),
                            volume=r.get('volume'),
                            issue=r.get('issue'),
                            pages=r.get('pages'),
                            doi=r.get('doi'),
                            url=r.get('url'),
                            ref_type=r.get('ref_type')
                        ))
                context.user_data['references'] = refs
            
            analyses_count = len(task['context'].get('analysis_history', []))
            refs_count = len(task['context'].get('references', []))
            
            await query.edit_message_text(
                f"✅ **Project Loaded!**\n\n"
                f"📝 **Title:** {task['title']}\n"
                f"🎯 **Objectives:** {task['context'].get('research_objectives', 'N/A')[:80]}...\n"
                f"📊 **Analyses saved:** {analyses_count}\n"
                f"📚 **References:** {refs_count}\n\n"
                "Please send any message to continue...",
                parse_mode='Markdown'
            )
            
            # Set a flag so next message shows action menu
            context.user_data['show_menu_on_next'] = True
        else:
            await query.edit_message_text("❌ Task not found.")
    
    elif query.data == "history_back":
        await query.edit_message_text("Use /start to begin a new analysis.")





async def save_and_exit_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Multi-step save handler that collects project metadata before saving."""
    file_path = context.user_data.get('file_path', '')
    
    if not file_path:
        await update.message.reply_text("❌ No active analysis to save.")
        return ConversationHandler.END
    
    # Check current save step
    save_step = context.user_data.get('save_step', 'start')
    
    if save_step == 'start':
        # Start save wizard - ask for title
        context.user_data['save_step'] = 'title'
        current_title = context.user_data.get('research_title', '')
        
        await update.message.reply_text(
            "💾 **Save Project**\n\n"
            "Let's save your analysis with details for easy retrieval.\n\n"
            f"**Step 1/4: Project Title**\n"
            f"Current: {current_title or 'Not set'}\n\n"
            "Enter a title for your project (or type 'skip' to keep current):",
            parse_mode='Markdown',
            reply_markup=ReplyKeyboardMarkup([['⏭️ Skip', '❌ Cancel Save']], one_time_keyboard=True)
        )
        return SAVE_PROJECT
    
    return SAVE_PROJECT


async def save_project_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the multi-step save project flow."""
    choice = update.message.text
    save_step = context.user_data.get('save_step', 'title')
    
    # Cancel save
    if choice == '❌ Cancel Save' or choice.lower() == 'cancel':
        context.user_data['save_step'] = None
        await show_action_menu(update, "Save cancelled.")
        return ACTION
    
    # Step 1: Title
    if save_step == 'title':
        if choice != '⏭️ Skip' and choice.lower() != 'skip':
            context.user_data['research_title'] = choice
        
        context.user_data['save_step'] = 'objectives'
        current = context.user_data.get('research_objectives', '')
        
        await update.message.reply_text(
            f"✅ Title: **{context.user_data.get('research_title', 'Untitled')}**\n\n"
            f"**Step 2/4: Research Objectives**\n"
            f"Current: {current[:100] if current else 'Not set'}{'...' if len(current) > 100 else ''}\n\n"
            "Enter your research objectives (or type 'skip'):",
            parse_mode='Markdown',
            reply_markup=ReplyKeyboardMarkup([['⏭️ Skip', '❌ Cancel Save']], one_time_keyboard=True)
        )
        return SAVE_PROJECT
    
    # Step 2: Objectives
    elif save_step == 'objectives':
        if choice != '⏭️ Skip' and choice.lower() != 'skip':
            context.user_data['research_objectives'] = choice
        
        context.user_data['save_step'] = 'questions'
        current = context.user_data.get('research_questions', '')
        
        await update.message.reply_text(
            f"✅ Objectives saved!\n\n"
            f"**Step 3/4: Research Questions**\n"
            f"Current: {current[:100] if current else 'Not set'}{'...' if len(current) > 100 else ''}\n\n"
            "Enter your research questions (or type 'skip'):",
            parse_mode='Markdown',
            reply_markup=ReplyKeyboardMarkup([['⏭️ Skip', '❌ Cancel Save']], one_time_keyboard=True)
        )
        return SAVE_PROJECT
    
    # Step 3: Research Questions
    elif save_step == 'questions':
        if choice != '⏭️ Skip' and choice.lower() != 'skip':
            context.user_data['research_questions'] = choice
        
        context.user_data['save_step'] = 'hypotheses'
        current = context.user_data.get('research_hypothesis', '')
        
        await update.message.reply_text(
            f"✅ Questions saved!\n\n"
            f"**Step 4/4: Hypotheses**\n"
            f"Current: {current[:100] if current else 'Not set'}{'...' if len(current) > 100 else ''}\n\n"
            "Enter your hypotheses (or type 'skip'):",
            parse_mode='Markdown',
            reply_markup=ReplyKeyboardMarkup([['⏭️ Skip', '❌ Cancel Save']], one_time_keyboard=True)
        )
        return SAVE_PROJECT
    
    # Step 4: Hypotheses & Save
    elif save_step == 'hypotheses':
        if choice != '⏭️ Skip' and choice.lower() != 'skip':
            context.user_data['research_hypothesis'] = choice
        
        # Now save to database
        user_id = update.message.from_user.id
        db = DatabaseManager()
        
        file_path = context.user_data.get('file_path', '')
        title = context.user_data.get('research_title', 'Untitled Analysis')
        
        # Prepare context data for saving (Sanitize for JSON)
        clean_history = []
        import pandas as pd
        for item in context.user_data.get('analysis_history', []):
            clean_item = item.copy()
            # Convert any DataFrame in 'data' to dict
            if 'data' in clean_item:
                if isinstance(clean_item['data'], pd.DataFrame):
                    clean_item['data'] = clean_item['data'].reset_index().to_dict(orient='records')
                elif isinstance(clean_item['data'], dict):
                     # Deep check for nested dfs? Usually flat.
                     pass 
            clean_history.append(clean_item)

        save_data = {
            'research_title': context.user_data.get('research_title', ''),
            'research_objectives': context.user_data.get('research_objectives', ''),
            'research_questions': context.user_data.get('research_questions', ''),
            'research_hypothesis': context.user_data.get('research_hypothesis', ''),
            'analysis_history': clean_history,
            'references': [{'title': r.title, 'authors': r.authors, 'year': r.year, 'source': r.source} 
                          for r in context.user_data.get('references', []) if hasattr(r, 'title')],
            'columns': context.user_data.get('columns', []),
            'num_cols': context.user_data.get('num_cols', []),
            'manuscript_settings': context.user_data.get('manuscript_settings', {})
        }
        
        task_id = db.save_task(
            user_id=user_id,
            title=title,
            file_path=file_path,
            context_data=save_data,
            status='saved'
        )
        
        # Show summary
        analyses_count = len(context.user_data.get('analysis_history', []))
        refs_count = len(context.user_data.get('references', []))
        
        context.user_data['save_step'] = None
        
        await update.message.reply_text(
            f"💾 **Project Saved Successfully!**\n\n"
            f"📋 **ID:** #{task_id}\n"
            f"📝 **Title:** {title}\n"
            f"🎯 **Objectives:** {context.user_data.get('research_objectives', 'N/A')[:50]}...\n"
            f"❓ **Questions:** {context.user_data.get('research_questions', 'N/A')[:50]}...\n"
            f"📊 **Analyses:** {analyses_count}\n"
            f"📚 **References:** {refs_count}\n\n"
            "Use **/history** to continue this project later.\n"
            "Use **/start** to begin a new project.",
            parse_mode='Markdown',
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END
    
    # Default
    return SAVE_PROJECT



# ---------------------------------------------------
#  Advanced Chart Configuration Handlers
# ---------------------------------------------------

async def chart_options_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Display the chart configuration menu."""
    config = context.user_data.get('chart_config', {})
    
    # Toggle states
    grid_state = "✅" if config.get('grid') else "⬜"
    legend_state = "✅" if config.get('legend') else "⬜"
    labels_state = "✅" if config.get('data_labels') else "⬜"
    orient_state = "Horizontal ↔️" if config.get('orientation') == 'h' else "Vertical ↕️"
    
    # Value states
    palette = config.get('palette', 'viridis')
    label_pos = config.get('label_pos', 'edge')
    
    # Text states
    title_text = config.get('title', 'Set Title')

    text = (f"🎨 **Customize Chart**\n"
            f"Type: `{context.user_data.get('chart_type')}`\n"
            f"Variable: `{context.user_data.get('chart_var')}`\n\n"
            f"**Current Settings:**\n"
            f"• Title: _{title_text}_\n"
            f"• Orientation: {orient_state}\n"
            f"• Palette: `{palette}`\n"
            f"• Data Labels: {labels_state} (Pos: {label_pos})\n"
            f"• Grid: {grid_state} | Legend: {legend_state}")

    keyboard = [
        [f"🔄 {orient_state}"],
        [f"🎨 Palette: {palette}", f"📍 Label Pos: {label_pos}"],
        [f"G: {grid_state} Grid", f"L: {legend_state} Legend", f"D: {labels_state} Labels"],
        ["📝 Edit Title", "🏷️ X Label", "🏷️ Y Label"],
        ["✅ Generate Chart", "❌ Cancel"]
    ]
    
    await update.message.reply_text(
        text,
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True),
        parse_mode='Markdown'
    )
    return CHART_CONFIG

async def chart_config_input_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process chart configuration inputs."""
    user_input = update.message.text
    config = context.user_data.get('chart_config', {})
    
    # Check if we are waiting for text input
    if context.user_data.get('awaiting_chart_text_input'):
        field = context.user_data['awaiting_chart_text_input']
        config[field] = user_input
        context.user_data['chart_config'] = config
        context.user_data['awaiting_chart_text_input'] = None # Reset
        return await chart_options_handler(update, context)

    # Toggle Logic
    if "Grid" in user_input:
        config['grid'] = not config.get('grid', False)
    elif "Legend" in user_input:
        config['legend'] = not config.get('legend', False)
    elif "Labels" in user_input:
        config['data_labels'] = not config.get('data_labels', False)
    elif "Horizontal" in user_input or "Vertical" in user_input:
        current = config.get('orientation', 'v')
        config['orientation'] = 'v' if current == 'h' else 'h'
        
    elif "Palette" in user_input:
        opts = ['viridis', 'magma', 'plasma', 'Blues', 'Reds', 'Set2']
        curr = config.get('palette', 'viridis')
        try:
            idx = opts.index(curr)
            config['palette'] = opts[(idx + 1) % len(opts)]
        except:
            config['palette'] = 'viridis'

    elif "Label Pos" in user_input:
        opts = ['edge', 'center', 'base']
        curr = config.get('label_pos', 'edge')
        try:
            idx = opts.index(curr)
            config['label_pos'] = opts[(idx + 1) % len(opts)]
        except:
             config['label_pos'] = 'edge'
        
    # Text Inputs
    elif user_input == "📝 Edit Title":
        context.user_data['awaiting_chart_text_input'] = 'title'
        await update.message.reply_text("⌨️ **Enter new chart title:**", reply_markup=ReplyKeyboardRemove())
        return CHART_CONFIG
    elif user_input == "🏷️ X Label":
        context.user_data['awaiting_chart_text_input'] = 'xlabel'
        await update.message.reply_text("⌨️ **Enter X-axis label:**", reply_markup=ReplyKeyboardRemove())
        return CHART_CONFIG
    elif user_input == "🏷️ Y Label":
        context.user_data['awaiting_chart_text_input'] = 'ylabel'
        await update.message.reply_text("⌨️ **Enter Y-axis label:**", reply_markup=ReplyKeyboardRemove())
        return CHART_CONFIG

    # Actions
    elif user_input == "✅ Generate Chart":
        await update.message.reply_text("🎨 Generating custom chart...")
        try:
            df = FileManager.get_active_dataframe(context.user_data.get('file_path'))
            chart_type = context.user_data.get('chart_type')
            var = context.user_data.get('chart_var')
            
            path = None
            if "Bar" in chart_type:
                path = Visualizer.create_bar_chart(df, var, config=config)
            elif "Pie" in chart_type:
                path = Visualizer.create_pie_chart(df, var, config=config)
            elif "Line" in chart_type:
                 # Adapt for single variable line chart (Trend of counts)
                counts = df[var].value_counts().sort_index().reset_index()
                counts.columns = [var, 'Count']
                path = Visualizer.create_line_chart(counts, x=var, y='Count', config=config)
            elif "Histogram" in chart_type:
                path = Visualizer.create_histogram(df, var, config=config)
            
            if path:
                # Capture data for manuscript appendix "Editable Data"
                chart_data = None
                try:
                    if "Bar" in chart_type or "Pie" in chart_type:
                        if "Bar" in chart_type and not df.empty:
                            # Replicate logic for data capture
                            # This is a bit duplicative but robust without refactoring Visualizer entirely
                             if df[var].dtype.kind in 'fi': # numeric?
                                 chart_data = df.groupby(var).mean().reset_index().to_dict()
                             else:
                                 chart_data = df[var].value_counts().reset_index().to_dict()
                        elif "Pie" in chart_type and not df.empty:
                             chart_data = df[var].value_counts().reset_index().to_dict()
                    elif "Line" in chart_type:
                        # For line chart logic used above
                         chart_data = counts.to_dict()
                    elif "Histogram" in chart_type:
                        # For histogram, provide descriptive stats as the "data table"
                        chart_data = df[var].describe().reset_index().to_dict()
                except:
                    pass

                await update.message.reply_photo(photo=open(path, 'rb'), caption=f"📊 {config.get('title')}")
                
                if 'visuals_history' not in context.user_data: 
                    context.user_data['visuals_history'] = []
                
                # Store rich object instead of just path
                context.user_data['visuals_history'].append({
                    'path': path,
                    'title': config.get('title'),
                    'type': chart_type,
                    'data': chart_data
                })
                
        except Exception as e:
            await update.message.reply_text(f"⚠️ Error: {e}")
        
        await show_action_menu(update)
        return ACTION

    elif user_input == "❌ Cancel":
        await show_action_menu(update)
        return ACTION

    # Save Update
    context.user_data['chart_config'] = config
    return await chart_options_handler(update, context)

async def ai_chat_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle free-form text with AI context awareness."""
    user_input = update.message.text
    
    # Ignore short or irrelevant messages if needed, but for now respond to all
    if len(user_input) < 2: return
    
    # Indicate typing
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')
    
    from src.core.ai_interpreter import AIInterpreter
    interpreter = AIInterpreter()
    
    file_path = context.user_data.get('file_path')
    history = context.user_data.get('analysis_history', [])
    
    response = await interpreter.chat(user_input, file_path=file_path, analysis_history=history)
    
    await update.message.reply_text(response, parse_mode='Markdown')

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Operation cancelled.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END
