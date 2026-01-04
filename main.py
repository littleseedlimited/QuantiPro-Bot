import os
import sys
import logging
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, PicklePersistence

# Load environment variables
load_dotenv()

# Logging setup
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

from src.bot.constants import (
    UPLOAD, ACTION, MANUSCRIPT_REVIEW, VISUAL_SELECT, SAVE_PROJECT,
    RESEARCH_TITLE, RESEARCH_OBJECTIVES, RESEARCH_QUESTIONS, RESEARCH_HYPOTHESIS,
    GOAL_SELECT, VAR_SELECT_1, VAR_SELECT_2, CONFIRM_ANALYSIS, POST_ANALYSIS,
    MODE_SELECT, METHOD_SELECT, CI_SELECT, PARAM_INPUT, STUDY_TYPE_SELECT, POPULATION_CHECK,
    S_NAME, S_EMAIL, S_PHONE, S_COUNTRY,
    TEST_SELECT, VAR_SELECT_GROUP, VAR_SELECT_TEST, ANOVA_SELECT_FACTOR, ANOVA_SELECT_DV, RELIABILITY_SELECT,
    GUIDE_CONFIRM, S_ID, CHART_CONFIG
)
from src.bot.handlers import (
    start_handler, file_handler, action_handler, plans_handler, force_admin_init,
    myplan_handler, profile_handler, signup_command_handler, profile_callback_handler,
    manuscript_review_handler, visual_select_handler,
    history_handler, admin_handler, admin_callback_handler, save_and_exit_handler,
    save_project_handler, payment_callback_handler, pre_checkout_handler, successful_payment_handler,
    help_handler, join_command_handler, ping_handler,
    cancel, chart_config_input_handler
)
from src.bot.admin_commands import (
    admin_users_command, admin_ban_command, admin_unban_command, 
    admin_delete_command, admin_upgrade_command
)

from src.bot.interview import InterviewManager
from src.bot.signup import SignupManager
from src.bot.sampling_handlers import (
    method_select_handler, ci_select_handler, param_input_handler,
    mode_select_handler, study_type_handler, population_check_handler
)
from src.bot.analysis_handlers import (
    start_hypothesis, start_reliability, test_select_handler, group_var_handler, test_var_handler,
    anova_factor_handler, anova_dv_handler, reliability_select_handler, guide_confirm_handler
)
from src.bot.project_handlers import project_callback_handler
from src.database.db_manager import DatabaseManager
from telegram.ext import ConversationHandler, MessageHandler, filters, CallbackQueryHandler

# Ensure UTF-8 output even on Windows terminals
try:
    if sys.stdout.encoding.lower() != 'utf-8':
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8')
        if hasattr(sys.stderr, 'reconfigure'):
            sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Exception while handling an update:", exc_info=context.error)
    print(f"CRITICAL HANDLER ERROR: {repr(context.error)}")
    import traceback
    traceback.print_exc()
    
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(
                f"❌ **An internal error occurred.**\n\nError: `{str(context.error)}`",
                parse_mode='Markdown'
            )
        except: pass

async def debug_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if update.message:
            text = update.message.text or "[Non-text message]"
            print(f"DEBUG: Message from {update.effective_user.id}: {ascii(text)}")
            logging.info(f"Update from {update.effective_user.id}: {text}")
        elif update.callback_query:
            print(f"DEBUG: Callback from {update.effective_user.id}: {update.callback_query.data}")
            logging.info(f"Callback from {update.effective_user.id}: {update.callback_query.data}")
        else:
            # print(f"DEBUG: Received update type: {type(update)}")
            pass
    except Exception as e:
        print(f"DEBUG: Handler log error: {repr(e)}")

def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        logging.error("TELEGRAM_BOT_TOKEN not found in environment variables.")
        # Create a dummy token for local testing if needed, or just exit.
        print("Please set TELEGRAM_BOT_TOKEN in .env")
        return

    # Init DB
    print("DEBUG: Initializing Database...")
    db = DatabaseManager()
    print("DEBUG: Database Initialized.")

    # Ensure only one instance
    print("DEBUG: Checking for other instances...")
    import socket
    try:
        # We use a global variable to keep the socket alive
        global _lock_socket
        _lock_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        _lock_socket.settimeout(0)
        _lock_socket.bind(("127.0.0.1", 45678))
        print("DEBUG: Socket lock acquired.")
    except socket.error:
        print("\nERROR: Another instance of the bot is already running.")
        print("Please close it before starting a new one.\n")
        return

    # Persistence
    print("DEBUG: Loading Persistence...")
    try:
        persistence = PicklePersistence(filepath='bot_data.pickle')
        print("DEBUG: Persistence Loaded.")
    except Exception as e:
        print(f"DEBUG: Persistence Error: {e}")
        persistence = None

    print("DEBUG: Building Application...")
    application = ApplicationBuilder().token(token)\
        .read_timeout(30)\
        .connect_timeout(30)\
        .write_timeout(30)\
        .persistence(persistence)\
        .build()
    print("DEBUG: Application Built.")
    application.add_error_handler(error_handler)

    # Conversation Handler
    print("DEBUG: Setting up handlers...")
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('start', start_handler),
            MessageHandler(filters.Regex(r'^📊 Analyse Data \(Upload File\)$'), action_handler),
            MessageHandler(filters.Regex(r'^🔢 Calculate Sample Size$'), action_handler),
            MessageHandler(filters.Regex(r'^📝 Generate Report$'), action_handler),
            MessageHandler(filters.Regex(r'^💬 AI Chat$'), action_handler),
            MessageHandler(filters.Regex(r'^📉 Describe & Explore$'), action_handler),
            MessageHandler(filters.Regex(r'^🆚 Hypothesis Tests$'), action_handler),
            MessageHandler(filters.Regex(r'^🔗 Relationships & Models$'), action_handler),
            MessageHandler(filters.Regex(r'^◀️ Back to Menu$'), action_handler),
        ],
        states={
            UPLOAD: [
                MessageHandler(filters.Document.ALL, file_handler),
                MessageHandler(filters.TEXT & ~filters.COMMAND, action_handler)
            ],
            ACTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, action_handler)],
            # Signup States
            S_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, SignupManager.handle_id)],
            S_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, SignupManager.handle_name)],
            S_EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, SignupManager.handle_email)],
            S_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, SignupManager.handle_phone)],
            S_COUNTRY: [MessageHandler(filters.TEXT & ~filters.COMMAND, SignupManager.handle_country)],
            # Interview States
            RESEARCH_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, InterviewManager.handle_title)],
            RESEARCH_OBJECTIVES: [MessageHandler(filters.TEXT & ~filters.COMMAND, InterviewManager.handle_objectives)],
            RESEARCH_QUESTIONS: [MessageHandler(filters.TEXT & ~filters.COMMAND, InterviewManager.handle_questions)],
            RESEARCH_HYPOTHESIS: [MessageHandler(filters.TEXT & ~filters.COMMAND, InterviewManager.handle_hypothesis)],
            GOAL_SELECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, InterviewManager.handle_goal)],
            VAR_SELECT_1: [MessageHandler(filters.TEXT & ~filters.COMMAND, InterviewManager.handle_var1)],
            VAR_SELECT_2: [MessageHandler(filters.TEXT & ~filters.COMMAND, InterviewManager.handle_var2)],
            CONFIRM_ANALYSIS: [MessageHandler(filters.TEXT & ~filters.COMMAND, InterviewManager.perform_analysis)],
            POST_ANALYSIS: [MessageHandler(filters.TEXT & ~filters.COMMAND, InterviewManager.handle_post_analysis)],
            # Manuscript & Visual States
            MANUSCRIPT_REVIEW: [MessageHandler(filters.TEXT & ~filters.COMMAND, manuscript_review_handler)],
            VISUAL_SELECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, visual_select_handler)],
            # Save Project State
            SAVE_PROJECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_project_handler)],
            
            # Sampling States
            MODE_SELECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, mode_select_handler)],
            STUDY_TYPE_SELECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, study_type_handler)],
            POPULATION_CHECK: [MessageHandler(filters.TEXT & ~filters.COMMAND, population_check_handler)],
            METHOD_SELECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, method_select_handler)],
            CI_SELECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, ci_select_handler)],
            PARAM_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, param_input_handler)],
            
            # Analysis States (New)
            TEST_SELECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, test_select_handler)],
            VAR_SELECT_GROUP: [MessageHandler(filters.TEXT & ~filters.COMMAND, group_var_handler)],
            VAR_SELECT_TEST: [MessageHandler(filters.TEXT & ~filters.COMMAND, test_var_handler)],
            ANOVA_SELECT_FACTOR: [MessageHandler(filters.TEXT & ~filters.COMMAND, anova_factor_handler)],
            ANOVA_SELECT_DV: [MessageHandler(filters.TEXT & ~filters.COMMAND, anova_dv_handler)],
            RELIABILITY_SELECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, reliability_select_handler)],
            GUIDE_CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, guide_confirm_handler)],
            CHART_CONFIG: [MessageHandler(filters.TEXT & ~filters.COMMAND, chart_config_input_handler)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        allow_reentry=True
    )


    # Debug Handler (Group -1 runs for everything)
    application.add_handler(MessageHandler(filters.ALL, debug_handler), group=-1)
    
    async def catch_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.message:
            print(f"DEBUG: Unhandled message in group 0: {update.message.text}")
    
    application.add_handler(conv_handler)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, catch_all))
    application.add_handler(CommandHandler('plans', plans_handler))
    application.add_handler(CommandHandler('myplan', myplan_handler))
    application.add_handler(CommandHandler('profile', profile_handler))
    application.add_handler(CommandHandler('signup', signup_command_handler))
    application.add_handler(CommandHandler('history', history_handler))
    application.add_handler(CommandHandler('admin', admin_handler))
    application.add_handler(CommandHandler('force_admin', force_admin_init))
    # Admin Management Commands
    application.add_handler(CommandHandler('users', admin_users_command))
    application.add_handler(CommandHandler('ban', admin_ban_command))
    application.add_handler(CommandHandler('unban', admin_unban_command))
    application.add_handler(CommandHandler('delete', admin_delete_command))
    application.add_handler(CommandHandler('upgrade', admin_upgrade_command))
    
    application.add_handler(CommandHandler('save', save_and_exit_handler))
    application.add_handler(CommandHandler('help', help_handler))
    application.add_handler(CommandHandler('join', join_command_handler))
    application.add_handler(CommandHandler('ping', ping_handler))
    application.add_handler(CallbackQueryHandler(admin_callback_handler, pattern='^(admin_|load_task_|history_)'))
    application.add_handler(CallbackQueryHandler(payment_callback_handler, pattern='^(select_|pay_|billing_|back_to_plans|show_yearly)'))
    application.add_handler(CallbackQueryHandler(project_callback_handler, pattern='^project_'))
    application.add_handler(CallbackQueryHandler(profile_callback_handler))
    
    # Payment handlers for Telegram Stars
    from telegram.ext import PreCheckoutQueryHandler
    application.add_handler(PreCheckoutQueryHandler(pre_checkout_handler))
    application.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_handler))

    print("QuantiProBot is running...")
    application.run_polling()

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        import traceback
        print(f"CRITICAL ERROR: {e}")
        traceback.print_exc()
        with open("crash.log", "a") as f:
            f.write(f"\n--- CRASH AT {datetime.now()} ---\n")
            f.write(traceback.format_exc())
