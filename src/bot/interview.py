from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, filters
import pandas as pd
from src.core.analyzer import Analyzer
from src.core.ai_interpreter import AIInterpreter

from src.bot.constants import (
    RESEARCH_TITLE, RESEARCH_OBJECTIVES, RESEARCH_QUESTIONS, RESEARCH_HYPOTHESIS,
    GOAL_SELECT, VAR_SELECT_1, VAR_SELECT_2, CONFIRM_ANALYSIS, POST_ANALYSIS,
    UPLOAD, ACTION
)

def find_matching_column(df, col_name):
    """Find the actual column name in DataFrame that matches the input, handling spacing/casing."""
    if col_name in df.columns:
        return col_name
    
    # Try case-insensitive match
    col_lower = col_name.lower().strip()
    for c in df.columns:
        if c.lower().strip() == col_lower:
            return c
    
    # Try partial match (contains)
    for c in df.columns:
        if col_lower in c.lower() or c.lower() in col_lower:
            return c
    
    # Return original if no match found
    return col_name


class InterviewManager:
    """
    Manages the 'Interview' mode where the bot guides the user.
    """
    
    @staticmethod
    def format_variable_list(df, max_show=15):
        """Format variable list with types for display."""
        lines = []
        for i, col in enumerate(df.columns[:max_show], 1):
            # Escape characters for Markdown safety
            safe_col = col.replace('_', '\\_').replace('*', '\\*').replace('`', "'")
            var_type = "📊 Other"
            if dtype == 'object':
                var_type = "📝 Text"
            elif 'int' in str(dtype) or 'float' in str(dtype):
                var_type = "🔢 Numeric"
            
            lines.append(f"{i}. {safe_col} ({var_type})")
        
        if len(df.columns) > max_show:
            lines.append(f"... and {len(df.columns) - max_show} more")
        
        return "\n".join(lines)
    
    @staticmethod
    async def start_interview(update: Update, context: ContextTypes.DEFAULT_TYPE):
        # Initialize analysis history for this session
        if 'analysis_history' not in context.user_data:
            context.user_data['analysis_history'] = []
        
        # CLEAR STALE FLAGS
        awaiting_keys = [k for k in context.user_data.keys() if k.startswith('awaiting_')]
        for k in awaiting_keys:
            context.user_data[k] = False
        context.user_data['ai_chat_mode'] = False # Disable AI mode for guided interview
        context.user_data['selected_corr_vars'] = []
        context.user_data['crosstab_row_vars'] = []
        context.user_data['crosstab_col_vars'] = []
            
        await update.message.reply_text(
            "🕵️ **Research Interview Mode**\n\n"
            "I will guide you through a comprehensive research analysis.\n"
            "All analyses will be saved and included in your final report.\n\n"
            "First, what is the **Title** of your study?",
            parse_mode='Markdown',
            reply_markup=ReplyKeyboardMarkup([['🏠 Main Menu']], one_time_keyboard=True)
        )
        return RESEARCH_TITLE


    @staticmethod
    async def handle_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.message.text == '🏠 Main Menu':
            from src.bot.handlers import show_action_menu, ACTION
            await show_action_menu(update, "Returned to main menu.")
            return ACTION
            
        context.user_data['research_title'] = update.message.text
        
        await update.message.reply_text("⚙️ Analyzing topic and generating suggestions...")
        
        ai = AIInterpreter()
        suggestions = await ai.generate_research_suggestions(update.message.text)
        context.user_data['ai_suggestions'] = suggestions
        
        await update.message.reply_text(
            f"✅ Title: **{update.message.text}**\n\n"
            "I've prepared some research suggestions based on your topic. We'll see them in the next steps.\n\n"
            "Now, what are your **Primary Objectives**?",
             parse_mode='Markdown'
        )
        return RESEARCH_OBJECTIVES

    @staticmethod
    async def handle_objectives(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.message.text == '🏠 Main Menu':
            from src.bot.handlers import show_action_menu, ACTION
            await show_action_menu(update, "Returned to main menu.")
            return ACTION
            
        context.user_data['research_objectives'] = update.message.text
        
        suggestions = context.user_data.get('ai_suggestions', {})
        q_sugg_list = suggestions.get('questions', [])
        
        msg = "Select a **Research Question** type or type your own:"
        if q_sugg_list:
            if isinstance(q_sugg_list, list):
                # Clean formatting for each line
                q_formatted = "\n\n".join([f"• {q.strip()}" for q in q_sugg_list if q.strip()])
            else:
                # Fallback for string
                q_formatted = "\n\n".join([f"• {line.strip()}" for line in str(q_sugg_list).split('\n') if line.strip()])
            
            msg = (
                "Select a **Research Question** type, use a suggestion, or type your own:\n\n"
                f"**💡 Tips to consider**:\n{q_formatted}"
            )
        
        await update.message.reply_text(
            msg,
            parse_mode='Markdown',
            reply_markup=ReplyKeyboardMarkup([
                ['Is there a significant difference between groups?'],
                ['Is there a relationship between variables?'],
                ['Can we predict an outcome from predictors?'],
                ['What are the characteristics of the sample?'],
                ['📝 Tips to consider', 'Type my own question']
            ], one_time_keyboard=True)
        )
        return RESEARCH_QUESTIONS

    @staticmethod
    async def handle_questions(update: Update, context: ContextTypes.DEFAULT_TYPE):
        choice = update.message.text
        
        if choice == '🏠 Main Menu':
            from src.bot.handlers import show_action_menu, ACTION
            await show_action_menu(update, "Returned to main menu.")
            return ACTION
            
        if choice == 'Type my own question':
            await update.message.reply_text("Please type your **Research Question**:")
            return RESEARCH_QUESTIONS

        if choice == '📝 Tips to consider':
            suggestions = context.user_data.get('ai_suggestions', {})
            q_list = suggestions.get('questions', [])
            if isinstance(q_list, list):
                context.user_data['research_questions'] = "\n".join([f"{i+1}. {q}" for i, q in enumerate(q_list)])
            else:
                context.user_data['research_questions'] = str(q_list)
                
            await update.message.reply_text(f"✅ Questions set to AI suggestions:\n\n{context.user_data['research_questions']}")
        else:
            context.user_data['research_questions'] = choice
        
        # Show list of common hypotheses
        suggestions = context.user_data.get('ai_suggestions', {})
        h_sugg_list = suggestions.get('hypotheses', [])
        
        msg = "Select a **Hypothesis** type or type your own:"
        if h_sugg_list:
            if isinstance(h_sugg_list, list):
                h_formatted = "\n\n".join([f"• {h.strip()}" for h in h_sugg_list if h.strip()])
            else:
                h_formatted = "\n\n".join([f"• {line.strip()}" for line in str(h_sugg_list).split('\n') if line.strip()])

            msg = (
                "Select a **Hypothesis** type, use a suggestion, or type your own:\n\n"
                f"**🎓 Tips to consider**:\n{h_formatted}"
            )
        
        await update.message.reply_text(
            msg,
            parse_mode='Markdown',
            reply_markup=ReplyKeyboardMarkup([
                ['There is a significant difference between groups'],
                ['There is a significant relationship between X and Y'],
                ['X significantly predicts Y'],
                ['No hypothesis (exploratory study)'],
                ['🎓 Tips to consider', 'Type my own hypothesis']
            ], one_time_keyboard=True)
        )
        return RESEARCH_HYPOTHESIS

    @staticmethod
    async def handle_hypothesis(update: Update, context: ContextTypes.DEFAULT_TYPE):
        choice = update.message.text
        
        if choice == '🏠 Main Menu':
            from src.bot.handlers import show_action_menu, ACTION
            await show_action_menu(update, "Returned to main menu.")
            return ACTION
            
        if choice == '🎓 Tips to consider':
            suggestions = context.user_data.get('ai_suggestions', {})
            h_list = suggestions.get('hypotheses', [])
            if isinstance(h_list, list):
                context.user_data['research_hypothesis'] = "\n".join([f"H{i+1}: {h}" for i, h in enumerate(h_list)])
            else:
                context.user_data['research_hypothesis'] = str(h_list)
            await update.message.reply_text(f"✅ Hypotheses set to AI suggestions:\n\n{context.user_data['research_hypothesis']}")
        elif choice == 'Type my own hypothesis':
            await update.message.reply_text("Please type your **Hypothesis**:")
            return RESEARCH_HYPOTHESIS
        else:
            context.user_data['research_hypothesis'] = choice
        
        next_step = context.user_data.get('next_step')
        
        if next_step == 'upload':
            await update.message.reply_text(
                "✅ **Metadata Captured!**\n\n"
                f"Hypothesis: _{choice}_\n\n"
                "Now, please **upload your data file** (CSV or Excel) to begin the analysis.",
                parse_mode='Markdown',
                reply_markup=ReplyKeyboardMarkup([['❌ Cancel Analysis']], resize_keyboard=True)
            )
            return UPLOAD
            
        elif next_step == 'sampling':
            await update.message.reply_text("✅ **Metadata Captured!**")
            from src.bot.sampling_handlers import start_sampling
            return await start_sampling(update, context)
            
        await update.message.reply_text(
            f"Perfect. Metadata captured.\nHypothesis: _{choice}_\n\n"
            "Now, **what is your Analysis Goal?**",
            parse_mode='Markdown',
            reply_markup=ReplyKeyboardMarkup([
                ['Compare Groups'],
                ['Find Relationships (Correlate)'],
                ['Predict Outcome (Regression)'],
                ['Reliability Analysis'],
                ['Cancel']
            ], one_time_keyboard=True)
        )
        return GOAL_SELECT


    @staticmethod
    async def handle_goal(update: Update, context: ContextTypes.DEFAULT_TYPE):
        goal = update.message.text
        
        # Handle navigation
        if goal == '🏠 Main Menu':
            from src.bot.handlers import show_action_menu
            await show_action_menu(update, "Returned to main menu.")
            return ACTION
        
        if goal == 'Cancel':
            await update.message.reply_text("Cancelled. Use /start to begin again.", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        
        context.user_data['goal'] = goal
        
        # Get columns from previously loaded file
        cols = context.user_data.get('columns', [])
        file_path = context.user_data.get('file_path')
        
        if not cols or not file_path:
            await update.message.reply_text("❌ No data loaded. Please upload a file first.")
            return ConversationHandler.END

        # Load df for variable info
        from src.core.file_manager import FileManager
        df, _ = FileManager.load_file(file_path)
        
        # Show ALL variables with types
        var_list = InterviewManager.format_variable_list(df, max_show=20)
        
        # Create markup for variable selection (limit to 12 as per original intent, but now safe)
        from src.bot.handlers import get_column_markup
        markup = get_column_markup(cols, max_cols=12, back_label='🏠 Main Menu')
        
        if goal.startswith('Compare'):
            await update.message.reply_text(
                f"📊 **Available Variables:**\n\n{var_list}\n\n"
                "To compare groups, select a **Categorical Variable** (e.g., Gender, Treatment):\n\n"
                "💡 *Tip: This will run a T-Test or ANOVA comparing means across groups.*",
                parse_mode='Markdown',
                reply_markup=markup
            )
            return VAR_SELECT_1
            
        elif goal.startswith('Find'):
            await update.message.reply_text(
                f"📊 **Available Variables:**\n\n{var_list}\n\n"
                "Select your **First Variable** for correlation:\n\n"
                "💡 *Tip: Correlation measures the relationship between two numeric variables.*",
                parse_mode='Markdown',
                reply_markup=markup
            )
            return VAR_SELECT_1
        
        elif goal.startswith('Predict'):
            await update.message.reply_text(
                f"📊 **Available Variables:**\n\n{var_list}\n\n"
                "Select your **Outcome/Dependent Variable** (what you want to predict):\n\n"
                "💡 *Tip: Regression predicts an outcome based on one or more predictors.*",
                parse_mode='Markdown',
                reply_markup=markup
            )
            return VAR_SELECT_1

        elif goal.startswith('Reliability'):
            await update.message.reply_text(
                f"📊 **Available Variables:**\n\n{var_list}\n\n"
                "List the scale items to test (comma separated):\n"
                "Example: Q1, Q2, Q3, Q4\n\n"
                "💡 *Tip: Cronbach's Alpha measures internal consistency of a scale.*",
                parse_mode='Markdown',
                reply_markup=ReplyKeyboardMarkup([['🏠 Main Menu']], one_time_keyboard=True)
            )
            return VAR_SELECT_1

            
        else:
            await update.message.reply_text("Goal not understood.")
            return ConversationHandler.END

    @staticmethod
    async def handle_var1(update: Update, context: ContextTypes.DEFAULT_TYPE):
        var1 = update.message.text
        
        # Handle navigation
        if var1 == '🏠 Main Menu':
            from src.bot.handlers import show_action_menu
            await show_action_menu(update, "Returned to main menu.")
            return ACTION
        
        context.user_data['var1'] = var1
        
        cols = context.user_data.get('columns', [])
        file_path = context.user_data.get('file_path')
        
        # Load df for variable info
        from src.core.file_manager import FileManager
        df, _ = FileManager.load_file(file_path)
        var_list = InterviewManager.format_variable_list(df, max_show=15)
        
        # Create keyboard excluding selected variable
        keyboard = [[c] for c in cols[:12] if c != var1]
        keyboard.append(['🏠 Main Menu'])
        
        goal = context.user_data.get('goal')
        
        if goal.startswith('Reliability'):
            # For reliability, we take the comma list and jump to confirmation
            alpha_cols = [c.strip() for c in var1.split(',')]
            context.user_data['alpha_cols'] = [find_matching_column(df, c) for c in alpha_cols]
            await update.message.reply_text(
                f"✅ Selected for reliability test:\n{', '.join(context.user_data['alpha_cols'])}\n\n"
                "Shall I run Cronbach's Alpha?",
                reply_markup=ReplyKeyboardMarkup([['Yes, Run Analysis'], ['🏠 Main Menu']], one_time_keyboard=True)
            )
            context.user_data['suggested_test'] = 'reliability'
            return CONFIRM_ANALYSIS

        elif goal.startswith('Predict'):
            # For regression, allow multi-variable selection
            await update.message.reply_text(
                f"✅ Outcome variable: `{var1}`\n\n"
                f"📊 **Available Predictors:**\n{var_list}\n\n"
                "Select **Predictor Variable(s)**:\n"
                "• Click a single variable, OR\n"
                "• Type multiple variables separated by commas\n"
                "  Example: Age, Income, Education\n\n"
                "💡 *Tip: Multiple predictors create a Multiple Regression model.*",
                parse_mode='Markdown',
                reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
            )
        else:
            await update.message.reply_text(
                f"✅ Selected: `{var1}`\n\n"
                "Now select your **Second Variable**:",
                parse_mode='Markdown',
                reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
            )
        
        return VAR_SELECT_2



    @staticmethod
    async def handle_var2(update: Update, context: ContextTypes.DEFAULT_TYPE):
        var2 = update.message.text
        
        # Handle navigation
        if var2 == '🏠 Main Menu':
            from src.bot.handlers import show_action_menu, ACTION
            await show_action_menu(update, "Returned to main menu.")
            return ACTION
        
        context.user_data['var2'] = var2
        
        # Suggest Analysis
        goal = context.user_data.get('goal')
        suggestion = ""
        var1 = context.user_data.get('var1', '')
        
        # Parse multiple predictors if comma-separated
        if ',' in var2:
            predictors = [p.strip() for p in var2.split(',')]
            predictor_display = ", ".join(predictors)
        else:
            predictors = [var2]
            predictor_display = var2
        
        if goal.startswith('Compare'):
            suggestion = "Independent T-Test"
            context.user_data['suggested_test'] = 'ttest'
            test_explain = "This will compare mean values between groups."
        elif goal.startswith('Find'):
            suggestion = "Pearson Correlation"
            context.user_data['suggested_test'] = 'correlation'
            test_explain = "This will measure the linear relationship between variables."
        elif goal.startswith('Predict'):
            if len(predictors) > 1:
                suggestion = f"Multiple Regression ({len(predictors)} predictors)"
            else:
                suggestion = "Simple Linear Regression"
            context.user_data['suggested_test'] = 'regression'
            test_explain = "This will predict the outcome based on predictor(s)."
            
        await update.message.reply_text(
            f"✅ **Analysis Plan**\n\n"
            f"📌 **Goal:** {goal}\n"
            f"📊 **Outcome:** `{var1}`\n"
            f"📈 **Predictor(s):** `{predictor_display}`\n"
            f"🧪 **Test:** {suggestion}\n\n"
            f"💡 *{test_explain}*\n\n"
            "Ready to run analysis?",
            parse_mode='Markdown',
            reply_markup=ReplyKeyboardMarkup([['Yes, Run Analysis'], ['🏠 Main Menu']], one_time_keyboard=True)
        )
        return CONFIRM_ANALYSIS


    @staticmethod
    async def perform_analysis(update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = update.message.text
        
        # Handle navigation
        if text == '🏠 Main Menu':
            from src.bot.handlers import show_action_menu, ACTION
            await show_action_menu(update, "Returned to main menu.")
            return ACTION
        
        if text != 'Yes, Run Analysis':
            await update.message.reply_text("Analysis cancelled.", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
            
        test = context.user_data.get('suggested_test')
        file_path = context.user_data.get('file_path')
        goal = context.user_data.get('goal', '')
        
        # Load Data
        try:
            from src.core.file_manager import FileManager
            df, _ = FileManager.load_file(file_path)
        except Exception as e:
            await update.message.reply_text("❌ Error loading data file. Please try uploading it again.")
            return ConversationHandler.END
        
        # Fix column names using helper
        var1_raw = context.user_data.get('var1', '')
        var2_raw = context.user_data.get('var2', '')
        var1 = find_matching_column(df, var1_raw)
        var2 = find_matching_column(df, var2_raw)
        
        interpreter = AIInterpreter()
        result_text = "Error in analysis."
        analysis_record = None  # Store for history
        
        await update.message.reply_text("⚙️ Running analysis... please wait.")
        
        try:
            if test == 'ttest':
                res = Analyzer.run_ttest(df, var1, var2)
                
                if 'error' in res:
                    result_text = f"❌ {res['error']}"
                else:
                    interpretation = await interpreter.interpret_results('ttest', res)
                    result_text = (
                        f"📊 **T-Test Results**\n\n"
                        f"Variables: {var1} by {var2}\n"
                        f"t = {res['t_val']:.3f}, p = {res['p_val']:.4f}\n\n"
                        f"📝 Interpretation:\n{interpretation}"
                    )
                    analysis_record = {'test': 'T-Test', 'vars': f'{var1} by {var2}', 'result': result_text, 'data': res}

            elif test == 'correlation':
                 cols = [var1, var2]
                 res = Analyzer.get_correlation(df, columns=cols)
                 
                 if 'error' in res:
                     result_text = f"❌ {res['error']}"
                 else:
                     val = res['r_values'].iloc[0,1]
                     interpretation = await interpreter.interpret_results('correlation', {'r': val})
                     result_text = (
                         f"📉 **Correlation Results**\n\n"
                         f"Variables: {var1} & {var2}\n"
                         f"r = {val:.3f}\n\n"
                         f"📝 Interpretation:\n{interpretation}"
                     )
                     analysis_record = {'test': 'Correlation', 'vars': f'{var1} & {var2}', 'result': result_text, 'data': {'r': val}}
                 
            elif test == 'regression':
                # Use already matched var1 as outcome
                y = var1  # Outcome
                # Match predictor columns too
                predictors_raw = [v.strip() for v in var2_raw.split(',')]
                predictors = [find_matching_column(df, p) for p in predictors_raw]
                
                res = Analyzer.run_regression(df, predictors, y)
                
                if 'error' in res:
                     result_text = f"❌ {res['error']}"
                else:
                    interpretation = await interpreter.interpret_results('regression', res)
                    n_obs = res.get('n_observations', 'N/A')
                    result_text = (
                        f"📈 **Regression Results**\n\n"
                        f"Outcome: {y}\n"
                        f"Predictors: {', '.join(predictors)}\n\n"
                        f"R² = {res.get('r_squared', 0):.3f}\n"
                        f"Model p-value = {res.get('f_pvalue', 0):.4f}\n"
                        f"Observations: {n_obs}\n\n"
                        f"📝 Interpretation:\n{interpretation}"
                    )
                    analysis_record = {'test': 'Regression', 'vars': f'{y} ~ {", ".join(predictors)}', 'result': result_text, 'data': res}


            elif test == 'reliability':
                cols = context.user_data['alpha_cols']
                res = Analyzer.run_cronbach_alpha(df, cols)
                if 'error' in res:
                    result_text = f"❌ {res['error']}"
                else:
                    interpretation = await interpreter.interpret_results('reliability', res)
                    result_text = (
                        f"🛡️ **Reliability Analysis**\n\n"
                        f"Items: {', '.join(cols)}\n"
                        f"Cronbach's Alpha: {res['alpha']:.3f}\n"
                        f"Interpretation: {res['interpretation']}\n\n"
                        f"📝 Insight:\n{interpretation}"
                    )
                    analysis_record = {'test': 'Reliability', 'vars': ', '.join(cols), 'result': result_text, 'data': res}

            elif test == 'chi2':
                res = Analyzer.run_chi2(df, var1, var2)
                if 'error' in res:
                    result_text = f"❌ {res['error']}"
                else:
                    interpretation = await interpreter.interpret_results('chi2', res)
                    
                    # Generate contingency table for display
                    ct_res = Analyzer.crosstab(df, var1, var2)
                    ct_fmt = Analyzer.format_crosstab_mobile(ct_res)
                    
                    result_text = (
                        f"🎲 **Chi-Square Test**\n\n"
                        f"Variables: {var1} × {var2}\n"
                        f"χ² = {res['chi2']:.3f}, p = {res['p_val']:.4f}\n\n"
                        f"{ct_fmt}\n\n"
                        f"📝 Interpretation:\n{interpretation}"
                    )
                    analysis_record = {'test': 'Chi-Square', 'vars': f'{var1} × {var2}', 'result': result_text, 'data': res}


        except Exception as e:
            result_text = f"❌ Analysis Failed: {str(e)[:150]}"

        # Store analysis in history
        if analysis_record:
            if 'analysis_history' not in context.user_data:
                context.user_data['analysis_history'] = []
            context.user_data['analysis_history'].append(analysis_record)
            count = len(context.user_data['analysis_history'])
            result_text = f"✅ Analysis #{count} saved to session.\n\n{result_text}"

        await update.message.reply_text(
            result_text, 
            parse_mode='Markdown', 
            reply_markup=ReplyKeyboardMarkup([
                ['📊 Run Another Analysis', '📋 Show Data'],
                ['📊 Create Visuals', '📄 Generate Report'],
                ['🏠 Main Menu', '✅ Finish']
            ], one_time_keyboard=True)
        )
        return POST_ANALYSIS


        return POST_ANALYSIS

    @staticmethod
    async def handle_post_analysis(update: Update, context: ContextTypes.DEFAULT_TYPE):
        choice = update.message.text
        
        # Helper to re-show post-analysis menu
        async def show_post_menu(msg=""):
            history_count = len(context.user_data.get('analysis_history', []))
            history_msg = f"📊 Analyses saved: {history_count}" if history_count else ""
            text = f"{msg}\n\n{history_msg}\n\n**What would you like to do next?**" if msg else f"{history_msg}\n\n**What would you like to do next?**"
            await update.message.reply_text(
                text,
                parse_mode='Markdown',
                reply_markup=ReplyKeyboardMarkup([
                    ['📊 Run Another Analysis', '📋 Show Data'],
                    ['📊 Create Visuals', '📄 Generate Report'],
                    ['🏠 Main Menu', '✅ Finish']
                ], one_time_keyboard=True)
            )
            return POST_ANALYSIS
        
        # Handle navigation
        if choice == '🏠 Main Menu':
            from src.bot.handlers import show_action_menu, ACTION
            await show_action_menu(update, "Returned to main menu.")
            return ACTION
        
        if choice == '📊 Run Another Analysis' or choice == 'Further Analysis':
            # Loop back to goal selection (NOT hypothesis)
            await update.message.reply_text(
                "Select your next Analysis Goal:",
                reply_markup=ReplyKeyboardMarkup([
                    ['Compare Groups'],
                    ['Find Relationships (Correlate)'],
                    ['Predict Outcome (Regression)'],
                    ['Reliability Analysis'],
                    ['Cancel']
                ], one_time_keyboard=True)
            )
            return GOAL_SELECT
        
        elif choice == '📋 Show Data' or choice == 'Show Data Table':
            file_path = context.user_data.get('file_path')
            try:
                from src.core.file_manager import FileManager
                df, _ = FileManager.load_file(file_path)
            except Exception as e:
                await update.message.reply_text("❌ Error loading data file.")
                return await show_post_menu()
            await update.message.reply_text(f"```\n{df.head(15).to_string()}\n```", parse_mode='Markdown')
            return await show_post_menu()
        
        elif choice == '📊 Create Visuals' or choice == 'Create Visuals':
            await update.message.reply_text("📊 Visual generation coming soon! For now, use the Report option.")
            return await show_post_menu()
        
        elif choice == '📄 Generate Report' or choice == 'Generate Report':
            try:
                await update.message.reply_text("📝 Generating comprehensive report with AI discussion... please wait.")
                from src.writing.generator import ManuscriptGenerator
                from src.core.file_manager import FileManager
                import os
                
                file_path = context.user_data.get('file_path')
                try:
                    from src.core.file_manager import FileManager
                    df, _ = FileManager.load_file(file_path)
                except Exception as e:
                    await update.message.reply_text("❌ Error loading data file.")
                    return await show_post_menu()

                
                gen = ManuscriptGenerator()
                
                # Collect all analyses from history
                analysis_history = context.user_data.get('analysis_history', [])
                stats_results = []
                
                # Add descriptive statistics
                desc_res = Analyzer.get_descriptive_stats(df).to_string()
                stats_results.append(f"Descriptive Statistics:\n{desc_res}")
                
                # Add all analyses from history
                for i, analysis in enumerate(analysis_history, 1):
                    stats_results.append(f"\nAnalysis {i}: {analysis['test']}\nVariables: {analysis['vars']}\n{analysis.get('result', '')}")
                
                # Generate AI Discussion section
                interpreter = AIInterpreter()
                discussion_text = await interpreter.generate_discussion(
                    title=context.user_data.get('research_title', 'Statistical Analysis'),
                    objectives=context.user_data.get('research_objectives', 'N/A'),
                    questions=context.user_data.get('research_questions', 'N/A'),
                    hypotheses=context.user_data.get('research_hypothesis', 'N/A'),
                    analysis_history=analysis_history,
                    descriptive_stats=desc_res
                )
                
                from src.bot.handlers import DATA_DIR
                base_name = os.path.basename(file_path).replace('.', '_')
                out_path = os.path.join(DATA_DIR, f"{base_name}_interview_report.docx")
                
                # Collect visuals
                visuals_history = context.user_data.get('visuals_history', [])
                
                gen.generate(
                    filename=out_path,
                    title=context.user_data.get('research_title', 'Statistical Analysis Report'),
                    authors=["QuantiProBot"],
                    abstract=f"This report contains {len(analysis_history)} analysis(es) performed via QuantiProBot Interview Mode.",
                    content_sections={
                        "Research Objectives": context.user_data.get('research_objectives', 'N/A'),
                        "Research Questions": context.user_data.get('research_questions', 'N/A'),
                        "Hypotheses": context.user_data.get('research_hypothesis', 'N/A')
                    },
                    stats_results=stats_results,
                    discussion_text=discussion_text,
                    images=visuals_history
                )
                await update.message.reply_document(
                    document=open(out_path, 'rb'), 
                    caption=f"📄 Your analysis report ({len(analysis_history)} analyses + AI Discussion)"
                )
                return await show_post_menu("📄 Report with Discussion generated successfully!")

            except Exception as e:
                await update.message.reply_text(f"⚠️ Error generating report: {str(e)[:150]}")
                return await show_post_menu()

        
        elif choice == '✅ Finish' or choice == 'Finish':
            history_count = len(context.user_data.get('analysis_history', []))
            await update.message.reply_text(
                f"✅ Session ended.\n\n"
                f"📊 Total analyses performed: {history_count}\n\n"
                "Use /start for a new analysis.", 
                reply_markup=ReplyKeyboardRemove()
            )
            return ConversationHandler.END
        
        # Default: unknown choice, re-show menu
        return await show_post_menu()



