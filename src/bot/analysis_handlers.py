from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, filters
from src.core.analyzer import Analyzer
from src.core.visualizer import Visualizer
from src.core.file_manager import FileManager
import pandas as pd
import os

from src.bot.constants import (
    TEST_SELECT, VAR_SELECT_GROUP, VAR_SELECT_TEST, ANOVA_SELECT_FACTOR, ANOVA_SELECT_DV, RELIABILITY_SELECT,
    GUIDE_CONFIRM, ACTION
)
from src.bot.analysis_utils import ANALYSIS_GUIDE

# --- HELPER: Dropdown/Keyboard Generator ---
def get_column_keyboard(df: pd.DataFrame, numeric_only=False, categorical_only=False):
    """Creates a ReplyKeyboardMarkup from dataframe columns to simulate a dropdown."""
    columns = df.columns.tolist()
    
    if numeric_only:
        columns = df.select_dtypes(include=['number']).columns.tolist()
    elif categorical_only:
        columns = df.select_dtypes(exclude=['number']).columns.tolist() # simplistic check
        # Add numeric columns with few unique values (potential factors)
        for col in df.select_dtypes(include=['number']).columns:
            if df[col].nunique() < 10:
                columns.append(col)
                
    # Create rows of 2 buttons
    keyboard = [columns[i:i + 2] for i in range(0, len(columns), 2)]
    keyboard.append(['◀️ Back to Menu'])
    return ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)

# --- ENTRY POINTS ---
async def start_hypothesis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Entry: Ask which test to run."""
    await update.message.reply_text(
        "🆚 **Hypothesis Testing**\n\n"
        "Select a test to learn more and proceed:",
        reply_markup=ReplyKeyboardMarkup([
            ['Independent T-Test (2 Groups)', 'One-Way ANOVA (3+ Groups)'],
            ['Mann-Whitney U (Non-Parametric)'],
            ['◀️ Back to Menu']
        ], one_time_keyboard=True, resize_keyboard=True)
    )
    return TEST_SELECT

async def show_guide(update: Update, context: ContextTypes.DEFAULT_TYPE, test_key: str):
    """Show explanation before starting variable selection."""
    guide = ANALYSIS_GUIDE.get(test_key)
    if not guide:
        # Fallback if key missing
        return await start_hypothesis(update, context)
        
    context.user_data['pending_test'] = test_key
    context.user_data['ai_chat_mode'] = False # Ensure AI chat is off during guided analysis
    
    text = (
        f"🧪 **{guide['name']}**\n\n"
        f"📝 **Description:**\n{guide['description']}\n\n"
        f"📊 **Variables Required:**\n`{guide['variables']}`\n\n"
        f"💡 **Use Case:**\n_{guide['use_case']}_\n\n"
        "Would you like to proceed with this analysis?"
    )
    
    await update.message.reply_text(
        text,
        parse_mode='Markdown',
        reply_markup=ReplyKeyboardMarkup([
            ['✅ Proceed', '❌ Cancel Analysis']
        ], one_time_keyboard=True, resize_keyboard=True)
    )
    return GUIDE_CONFIRM

async def guide_confirm_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the user's choice to proceed or cancel after reading the guide."""
    choice = update.message.text
    test_key = context.user_data.get('pending_test')
    
    if choice == '❌ Cancel Analysis':
        from src.bot.handlers import show_action_menu
        await show_action_menu(update, "Analysis cancelled.")
        return ACTION

    if not test_key:
        return ACTION

    # Ensure DF is loaded
    df = context.user_data.get('df')
    if df is None:
        file_path = context.user_data.get('file_path')
        if file_path:
            try:
                df = FileManager.get_active_dataframe(file_path)
                context.user_data['df'] = df
            except Exception:
                pass
        
    if df is None:
        await update.message.reply_text("⚠️ Dataset session lost or invalid. Please upload file again.")
        return ACTION

    # Route to appropriate starting point based on test
    if test_key in ['ttest', 'mwu']:
        context.user_data['current_test'] = test_key
        # Check if categorical vars exist
        cat_cols = df.select_dtypes(exclude=['number']).columns.tolist()
        if not cat_cols:
             # Fallback to text input or all cols if no strict cats found
             pass
             
        await update.message.reply_text(
            "1️⃣ **Select Grouping Variable** (Categorical):",
            reply_markup=get_column_keyboard(df, categorical_only=True)
        )
        return VAR_SELECT_GROUP
    elif test_key == 'anova':
        context.user_data['current_test'] = 'anova'
        await update.message.reply_text(
            "1️⃣ **Select Factor/Group Variable** (Categorical):",
            reply_markup=get_column_keyboard(df, categorical_only=True)
        )
        return ANOVA_SELECT_FACTOR
    elif test_key == 'correlation':
        context.user_data['awaiting_corr_vars'] = True
        context.user_data['selected_corr_vars'] = []
        num_cols = context.user_data.get('num_cols', [])
        from src.bot.handlers import get_column_markup
        await update.message.reply_text(
            "Select at least **2 Numeric Variables** for correlation:",
            reply_markup=get_column_markup(num_cols)
        )
        return ACTION
    elif test_key == 'regression':
        context.user_data['awaiting_regression_dep'] = True
        num_cols = context.user_data.get('num_cols', [])
        from src.bot.handlers import get_column_markup
        await update.message.reply_text(
            "Select the **Outcome (Dependent)** variable:",
            reply_markup=get_column_markup(num_cols)
        )
        return ACTION
    elif test_key == 'crosstab':
        context.user_data['awaiting_crosstab_row'] = True
        context.user_data['crosstab_row_vars'] = []
        all_cols = context.user_data.get('columns', [])
        from src.bot.handlers import get_column_markup
        await update.message.reply_text(
            "Select **ROW** variable(s):",
            reply_markup=get_column_markup(all_cols, extra_buttons=['✅ Done Selecting'])
        )
        return ACTION
    elif test_key == 'frequencies':
        context.user_data['awaiting_freq_vars'] = True
        context.user_data['freq_vars'] = []
        all_cols = context.user_data.get('columns', [])
        from src.bot.handlers import get_column_markup
        await update.message.reply_text(
            "Select variable(s) for **Frequency Tabulation**:",
            reply_markup=get_column_markup(all_cols, extra_buttons=['✅ Done Selecting'])
        )
        return ACTION
    elif test_key == 'descriptive':
        from src.bot.handlers import check_feature
        if not await check_feature(update, update.effective_user.id, 'descriptive_stats'): 
            from src.bot.handlers import show_action_menu
            await show_action_menu(update)
            return ACTION
            
        from src.core.analyzer import Analyzer
        from src.core.ai_interpreter import AIInterpreter
        
        await update.message.reply_text("🔄 Calculating Descriptive Statistics...")
        try:
            stats = Analyzer.get_descriptive_stats(df)
            
            # Generate text summary for history (always)
            text_summary = Analyzer.format_stats_mobile(stats)
            
            # SLEEK OPTION: Generate and send image
            img_path = Visualizer.create_stats_table_image(stats)
            
            if img_path and os.path.exists(img_path):
                with open(img_path, 'rb') as f:
                    await update.message.reply_photo(
                        photo=f,
                        caption="📊 **Descriptive Statistics Table**",
                        parse_mode='Markdown'
                    )
            else:
                # Fallback to text if image fails or visuals are disabled
                await update.message.reply_text(text_summary, parse_mode='Markdown')
            
            # Store for history
            if 'analysis_history' not in context.user_data:
                context.user_data['analysis_history'] = []
            context.user_data['analysis_history'].append({
                'test': 'Descriptive Statistics',
                'vars': 'All selected numeric columns',
                'result': text_summary,
                'data': stats.to_dict()
            })

            # Store for export
            context.user_data['last_analysis'] = {
                'type': 'descriptive_stats',
                'data': stats,
                'title': 'Descriptive Statistics'
            }
            
            # Log visual
            if img_path:
                if 'visuals_history' not in context.user_data:
                    context.user_data['visuals_history'] = []
                context.user_data['visuals_history'].append({
                    'path': img_path,
                    'title': 'Descriptive Statistics Table',
                    'type': 'stats_table',
                    'data': stats.to_dict()
                })
            
            # AI Interpretation with better formatting
            try:
                interpreter = AIInterpreter()
                ai_msg = await interpreter.interpret_results('descriptive', stats.to_dict())
                formatted_ai = f"📖 **Interpretation:**\n\n{ai_msg}"
                await update.message.reply_text(formatted_ai, parse_mode='Markdown')
            except Exception as e:
                pass  # Silently skip if AI interpretation fails
    
            # Store for history (use text_summary, not undefined msg)
            if 'analysis_history' not in context.user_data: context.user_data['analysis_history'] = []
            context.user_data['analysis_history'].append({
                'test': 'Descriptive Statistics',
                'vars': ', '.join(stats.index.tolist()),
                'result': text_summary,
                'data': stats.to_dict()
            })
            
            # Export to Excel immediately for convenience
            excel_path = f"data/descriptive_stats_{update.effective_user.id}.xlsx"
            try:
                stats.to_excel(excel_path)
                with open(excel_path, 'rb') as f:
                    await update.message.reply_document(
                        document=f,
                        filename="Descriptive_Statistics.xlsx",
                        caption="📥 **Your Descriptive Statistics (Excel)**\nYou can edit this file directly."
                    )
            except Exception as e:
                pass  # Silently continue if export fails
    
            await update.message.reply_text(
                "✅ Done! What would you like to do next?", 
                reply_markup=ReplyKeyboardMarkup([
                    ['📉 Describe & Explore', '🆚 Hypothesis Tests'],
                    ['🔗 Relationships & Models', '◀️ Back to Menu']
                ], one_time_keyboard=True, resize_keyboard=True)
            )
            return ACTION
        except Exception as e:
            import traceback
            traceback.print_exc()
            await update.message.reply_text(f"⚠️ An error occurred during analysis: {str(e)}")
            from src.bot.handlers import show_action_menu
            await show_action_menu(update)
            return ACTION

    elif test_key == 'frequencies':
        context.user_data['awaiting_tabulation_var'] = True
        all_cols = context.user_data.get('columns', [])
        from src.bot.handlers import get_column_markup
        await update.message.reply_text(
            "Select variable for frequency tabulation:",
            reply_markup=get_column_markup(all_cols)
        )
        return ACTION
    elif test_key == 'reliability':
        return await start_reliability(update, context)

    return ACTION

async def start_reliability(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Entry: Reliability Analysis."""
    df = context.user_data.get('df')
    if df is None:
        await update.message.reply_text("❌ No data loaded.")
        return ConversationHandler.END
        
    context.user_data['rel_items'] = []
    
    await update.message.reply_text(
        "🔗 **Reliability Analysis (Cronbach's Alpha)**\n\n"
        "Select items (variables) to include in the scale.\n"
        "**Click one by one**, then click **✅ Done**.",
        reply_markup=get_reliability_keyboard(df, [])
    )
    return RELIABILITY_SELECT

def get_reliability_keyboard(df, selected):
    """Dynamic keyboard for multi-select."""
    nums = df.select_dtypes(include=['number']).columns.tolist()
    remaining = [c for c in nums if c not in selected]
    
    # Rows of 2
    keyboard = [remaining[i:i + 2] for i in range(0, len(remaining), 2)]
    keyboard.append(['✅ Done', '◀️ Cancel'])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# --- HANDLERS ---

async def test_select_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    choice = update.message.text
    if 'Back' in choice: 
        from src.bot.handlers import show_action_menu
        await show_action_menu(update)
        return ACTION
    
    mapping = {
        'Independent T-Test': 'ttest',
        'One-Way ANOVA': 'anova',
        'Mann-Whitney U': 'mwu'
    }
    
    test_key = None
    for k, v in mapping.items():
        if k in choice:
            test_key = v
            break
            
    if test_key:
        return await show_guide(update, context, test_key)
    
    return TEST_SELECT

async def group_var_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    col = update.message.text
    df = context.user_data.get('df')
    
    if col == '◀️ Back to Menu': return ConversationHandler.END
    if col not in df.columns:
        await update.message.reply_text("⚠️ Column not found. Select from the menu.")
        return VAR_SELECT_GROUP

    # Validate 2 groups for T-Test
    unique = df[col].dropna().unique()
    if len(unique) != 2:
        await update.message.reply_text(
            f"⚠️ Variable '{col}' has {len(unique)} groups: {unique}.\n"
            "T-Tests require exactly **2 groups**.\n"
            "Please select a different grouping variable.",
            reply_markup=get_column_keyboard(df, categorical_only=True)
        )
        return VAR_SELECT_GROUP

    context.user_data['group_col'] = col
    await update.message.reply_text(
        "2️⃣ **Select Test Variable** (Numeric):\n"
        "_(e.g., Salary, Test Score)_",
        reply_markup=get_column_keyboard(df, numeric_only=True)
    )
    return VAR_SELECT_TEST

async def test_var_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    col = update.message.text
    df = context.user_data.get('df')
    
    if col == '◀️ Back to Menu': return ConversationHandler.END
    if col not in df.columns: return VAR_SELECT_TEST
    
    group_col = context.user_data['group_col']
    test_type = context.user_data.get('current_test', 'ttest')
    
    await update.message.reply_text(f"🔄 Running {test_type} on **{col}** by **{group_col}**...")
    
    if test_type == 'ttest':
        res = Analyzer.run_ttest(df, group_col, col)
    else:
        res = Analyzer.run_non_parametric(df, group_col, col)
        
    if "error" in res:
        await update.message.reply_text(f"❌ Error: {res['error']}")
    else:
        labels = context.user_data.get('variable_labels', {})
        col_lbl = f"{col} ({labels.get(col, '')})" if labels.get(col) else col
        grp_lbl = f"{group_col} ({labels.get(group_col, '')})" if labels.get(group_col) else group_col

        if test_type == 'ttest':
            msg = (f"✅ **Independent T-Test Results**\n\n"
                   f"Difference between groups in **{col_lbl}**:\n"
                   f"Grouping by: **{grp_lbl}**\n"
                   f"Groups: {res['groups']}\n\n"
                   f"**t-value**: {res['t_val']:.3f}\n"
                   f"**p-value**: {res['p_val']:.4f}\n"
                   f"**Cohen's d**: {res['cohen_d']:.3f}\n\n"
                   f"{'🌟 SIGNIFICANT difference!' if res['p_val'] < 0.05 else 'Outcome: No significant difference.'}")
        else:
             msg = (f"✅ **Mann-Whitney U Results**\n\n"
                    f"Variable: **{col_lbl}** by **{grp_lbl}**\n"
                    f"**U-val**: {res['U-val']}\n"
                    f"**p-val**: {res['p-val']:.4f}\n"
                    f"{'🌟 SIGNIFICANT' if res['p-val'] < 0.05 else 'Not Significant'}")
                    
        await update.message.reply_text(msg, parse_mode='Markdown')
        
        # Store for history
        if 'analysis_history' not in context.user_data: context.user_data['analysis_history'] = []
        context.user_data['analysis_history'].append({
            'test': 'Independent T-Test' if test_type == 'ttest' else 'Mann-Whitney U',
            'vars': f'{col} by {group_col}',
            'result': msg,
            'data': [res] # Wrapped in list for DataFrame conversion
        })
        
        # Store for export
        context.user_data['last_analysis'] = {
            'type': 'hypothesis_test',
            'data': [res], # Wrapped in list
            'title': f'{test_type}_{group_col}_{col}'
        }
        
        await update.message.reply_text(
            "📥 Export this result?",
            reply_markup=ReplyKeyboardMarkup([
                ['📥 Export to Excel', '📥 Export to CSV'],
                ['◀️ Back to Menu']
            ], one_time_keyboard=True, resize_keyboard=True)
        )
        
    return ConversationHandler.END

# --- ANOVA HANDLERS ---
async def anova_factor_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    col = update.message.text
    df = context.user_data.get('df')
    
    if col == '◀️ Back to Menu': return ConversationHandler.END
    if col not in df.columns: return ANOVA_SELECT_FACTOR
    
    # Check groups > 2
    if df[col].nunique() < 3:
        await update.message.reply_text("⚠️ ANOVA requires 3+ groups. Use T-Test for 2 groups.")
        return ANOVA_SELECT_FACTOR
        
    context.user_data['anova_factor'] = col
    await update.message.reply_text(
        "2️⃣ **Select Dependent Variable** (Numeric):",
        reply_markup=get_column_keyboard(df, numeric_only=True)
    )
    return ANOVA_SELECT_DV

async def anova_dv_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    col = update.message.text
    df = context.user_data.get('df')
    
    if col not in df.columns: return ANOVA_SELECT_DV
    
    factor = context.user_data['anova_factor']
    await update.message.reply_text(f"🔄 Running One-Way ANOVA: **{col} ~ {factor}**...")
    
    res_df = Analyzer.run_anova(df, dv=col, between=factor)
    
    if res_df.empty:
        await update.message.reply_text("❌ Analysis Failed.")
    else:
        # Format ANOVA table
        row = res_df.iloc[0]
        labels = context.user_data.get('variable_labels', {})
        dv_lbl = f"{col} ({labels.get(col, '')})" if labels.get(col) else col
        fac_lbl = f"{factor} ({labels.get(factor, '')})" if labels.get(factor) else factor
        
        msg = (f"✅ **ANOVA Results**\n\n"
               f"Dependent Var: **{dv_lbl}**\n"
               f"Factor: **{fac_lbl}**\n"
               f"**F-value**: {row['F']:.3f}\n"
               f"**p-value**: {row['p-unc']:.4f}\n"
               f"**np2** (Effect Size): {row['np2']:.3f}\n\n"
               f"{'🌟 SIGNIFICANT difference found.' if row['p-unc'] < 0.05 else 'No significant difference.'}")
        await update.message.reply_text(msg, parse_mode='Markdown')
        
        # Store for history
        if 'analysis_history' not in context.user_data: context.user_data['analysis_history'] = []
        context.user_data['analysis_history'].append({
            'test': 'One-Way ANOVA',
            'vars': f'{col} ~ {factor}',
            'result': msg,
            'data': res_df.to_dict()
        })
        
        # Store for export
        context.user_data['last_analysis'] = {
            'type': 'anova',
            'data': res_df,
            'title': f'ANOVA_{col}_{factor}'
        }
        
        await update.message.reply_text(
            "📥 Export this result?",
            reply_markup=ReplyKeyboardMarkup([
                ['📥 Export to Excel', '📥 Export to CSV'],
                ['◀️ Back to Menu']
            ], one_time_keyboard=True, resize_keyboard=True)
        )
        
    return ConversationHandler.END

# --- RELIABILITY HANDLERS ---
async def reliability_select_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    df = context.user_data.get('df')
    selected = context.user_data.get('rel_items', [])
    
    if text == '◀️ Cancel': return ConversationHandler.END
    
    if text == '✅ Done':
        if len(selected) < 2:
            await update.message.reply_text("⚠️ Need at least 2 items for reliability.")
            return RELIABILITY_SELECT
        
        # Run Analysis
        await update.message.reply_text(f"🔄 Calculating Cronbach's Alpha for: {', '.join(selected)}...")
        res = Analyzer.run_cronbach_alpha(df, selected)
        
        if "error" in res:
            await update.message.reply_text(f"❌ Error: {res['error']}")
        else:
            labels = context.user_data.get('variable_labels', {})
            # List truncated items with labels
            item_list = [f"{i} ({labels.get(i)})" if labels.get(i) else i for i in selected[:5]]
            if len(selected) > 5: item_list.append("...")
            
            msg = (f"✅ **Reliability Analysis**\n\n"
                   f"Items: {len(selected)}\n"
                   f"Vars: {', '.join(item_list)}\n"
                   f"**Cronbach's Alpha**: {res['alpha']:.3f}\n"
                   f"**95% CI**: {res['conf_interval']}\n"
                   f"**Rating**: {res['interpretation']}")
            await update.message.reply_text(msg, parse_mode='Markdown')
            
            # Store for history
            if 'analysis_history' not in context.user_data: context.user_data['analysis_history'] = []
            context.user_data['analysis_history'].append({
                'test': 'Reliability Analysis',
                'vars': ', '.join(selected),
                'result': msg,
                'data': res
            })
            
            # Store for export
            context.user_data['last_analysis'] = {
                'type': 'reliability',
                'data': {'items': selected, **res},
                'title': 'Cronbach_Alpha'
            }
            
            await update.message.reply_text(
                "📥 Export this result?",
                reply_markup=ReplyKeyboardMarkup([
                    ['📥 Export to Excel', '📥 Export to CSV'],
                    ['◀️ Back to Menu']
                ], one_time_keyboard=True, resize_keyboard=True)
            )
        return ConversationHandler.END
    
    if text in df.columns:
        if text not in selected:
            selected.append(text)
            context.user_data['rel_items'] = selected
            await update.message.reply_text(
                f"Added **{text}**. (Total: {len(selected)})\nSelect more or click Done.",
                reply_markup=get_reliability_keyboard(df, selected),
                parse_mode='Markdown'
            )
        else:
             await update.message.reply_text("Already selected.")
    else:
        await update.message.reply_text("⚠️ Invalid selection.")
        
    return RELIABILITY_SELECT
