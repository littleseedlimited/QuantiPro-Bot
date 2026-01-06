from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes, ConversationHandler
from src.core.sampler import Sampler

from src.bot.constants import (
    MODE_SELECT, STUDY_TYPE_SELECT, METHOD_SELECT, POPULATION_CHECK, CI_SELECT, PARAM_INPUT
)

async def start_sampling(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Entry point: Ask for Mode (Guided vs Direct)."""
    await update.message.reply_text(
        "🔢 **Sample Size Calculator**\n\n"
        "How would you like to proceed?",
        parse_mode='Markdown',
        reply_markup=ReplyKeyboardMarkup([
            ['🎓 Help me choose (Study Design)'],
            ['🛠️ I know the method (Direct Selection)'],
            ['◀️ Back to Main Menu']
        ], one_time_keyboard=True)
    )
    return MODE_SELECT

async def mode_select_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    choice = update.message.text
    
    if 'Back' in choice:
        await update.message.reply_text("Teleporting to Main Menu... use /start to restart.", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END

    if 'Help me choose' in choice:
        await update.message.reply_text(
            "🎓 **Select your Study Design:**\n\n"
            "1. **Cross-sectional / Survey**\n"
            "   _One-time data collection (e.g., opinion poll, prevalence)_.\n"
            "2. **Experimental / Comparative**\n"
            "   _Comparing groups (e.g., Treatment vs Control)_.\n"
            "3. **Correlational**\n"
            "   _Relationships between variables_.",
            parse_mode='Markdown',
            reply_markup=ReplyKeyboardMarkup([
                ['1. Cross-sectional (Survey)'],
                ['2. Experimental (Comparison)'],
                ['3. Correlational'],
                ['◀️ Back']
            ], one_time_keyboard=True)
        )
        return STUDY_TYPE_SELECT
    
    elif 'Direct' in choice:
        await update.message.reply_text(
            "🛠️ **Select Statistical Method:**",
            reply_markup=ReplyKeyboardMarkup([
                ['Cochran (Proportions)', 'Yamane (Finite Pop)'],
                ['Power Analysis (T-Test)'],
                ['◀️ Back']
            ], one_time_keyboard=True)
        )
        return METHOD_SELECT
    
    return await start_sampling(update, context)

async def study_type_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    choice = update.message.text
    if 'Back' in choice: return await start_sampling(update, context)

    if 'Cross-sectional' in choice:
        # Map to Cochran, but first check Population
        context.user_data['sampling_method'] = 'cochran'
        await update.message.reply_text(
            "📋 **Cross-sectional Study**\n"
            "Typically uses **Cochran's Formula**.\n\n"
            "**Question:** Do you know the exact size of your target population?",
            parse_mode='Markdown',
            reply_markup=ReplyKeyboardMarkup([
                ['Yes, I know N (Finite)', 'No / General Public (Infinite)'],
                ['Unsure (Help me decide)'],
                ['◀️ Back']
            ], one_time_keyboard=True)
        )
        return POPULATION_CHECK

    elif 'Experimental' in choice:
        # Map to Power Analysis
        context.user_data['sampling_method'] = 'power'
        await update.message.reply_text("🧪 **Experimental Study**\nUsing **Power Analysis** to detect effects.")
        return await ask_power_params(update)

    elif 'Correlational' in choice:
        # Simplified: Map to Power Analysis for now (or could use specific corr formula)
        context.user_data['sampling_method'] = 'power'
        await update.message.reply_text("📈 **Correlational Study**\nUsing **Power Analysis**.")
        return await ask_power_params(update)
    
    else:
        await update.message.reply_text("Please make a selection.")
        return STUDY_TYPE_SELECT

async def population_check_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    choice = update.message.text
    if 'Back' in choice: return MODE_SELECT # Go back start

    if 'Yes' in choice:
        # Finite Population
        context.user_data['sampling_method'] = 'cochran' # Use Cochran with correction
        await update.message.reply_text("Please enter the **Population Size (N)**:")
        context.user_data['awaiting_param'] = 'cochran_N'
        return PARAM_INPUT
    
    elif 'No' in choice:
        # Infinite
        context.user_data['sampling_method'] = 'cochran'
        context.user_data['param_N'] = None
        return await ask_confidence_interval(update)

    elif 'Unsure' in choice:
        # Guided question
        await update.message.reply_text(
            "🤔 **Let's figure it out.**\n\n"
            "Is your study targeting a **specific, listable group** (e.g., 'Employees of Google', 'Students at X High School')?\n"
            "OR\n"
            "A **general/uncountable group** (e.g., 'Residents of NY', 'iPhone users')?",
            parse_mode='Markdown',
            reply_markup=ReplyKeyboardMarkup([
                ['Specific/Listable (Finite)', 'General/Uncountable (Infinite)'],
                ['◀️ Back']
            ], one_time_keyboard=True)
        )
        return POPULATION_CHECK # Loop back with simplified choice

    elif 'Specific' in choice:
        await update.message.reply_text("Since it's a specific group, we treat it as **Finite**.\n\nPlease estimate the **Population Size (N)**:")
        context.user_data['awaiting_param'] = 'cochran_N'
        return PARAM_INPUT
        
    elif 'General' in choice:
        await update.message.reply_text("Since it's a general group, we treat it as **Infinite**.")
        context.user_data['param_N'] = None
        return await ask_confidence_interval(update)
    
    return POPULATION_CHECK

async def method_select_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    choice = update.message.text
    if 'Back' in choice: return await start_sampling(update, context)

    if 'Cochran' in choice:
        context.user_data['sampling_method'] = 'cochran'
        await update.message.reply_text("Use Finite Population Correction?", 
            reply_markup=ReplyKeyboardMarkup([['Yes', 'No']], one_time_keyboard=True))
        return POPULATION_CHECK # Re-use the Yes/No logic logic roughly or redirect

    elif 'Yamane' in choice:
        context.user_data['sampling_method'] = 'yamane'
        await update.message.reply_text("Enter **Population Size (N)**:")
        context.user_data['awaiting_param'] = 'yamane_N'
        return PARAM_INPUT

    elif 'Power' in choice:
        context.user_data['sampling_method'] = 'power'
        return await ask_power_params(update)

    return METHOD_SELECT

async def ask_power_params(update: Update):
    await update.message.reply_text(
        "**Power Analysis Parameters**\n\n"
        "We need the **Effect Size** (magnitude of difference).\n"
        "• Small: 0.2\n• Medium: 0.5 (Standard)\n• Large: 0.8",
        parse_mode='Markdown',
        reply_markup=ReplyKeyboardMarkup([
            ['Small (0.2)', 'Medium (0.5)', 'Large (0.8)'],
            ['Custom']
        ], one_time_keyboard=True)
    )
    return PARAM_INPUT

async def ask_confidence_interval(update: Update):
    # Educational Pre-text
    await update.message.reply_text(
        "⚙️ **Parameters Considered:**\n"
        "• **Confidence Level (Z)**: How sure you want to be.\n"
        "• **Precision (e)**: Margin of error (Standard is 5%).\n\n"
        "Select **Confidence Level**:",
        parse_mode='Markdown',
        reply_markup=ReplyKeyboardMarkup([
            ['95% (Standard)', '99% (High Precision)', '90%'],
            ['◀️ Back']
        ], one_time_keyboard=True)
    )
    return CI_SELECT

async def param_input_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    method = context.user_data.get('sampling_method')
    
    if text == '◀️ Back': return await start_sampling(update, context)

    # 1. COCHRAN N INPUT
    if method == 'cochran' and context.user_data.get('awaiting_param') == 'cochran_N':
        if not text.isdigit():
             await update.message.reply_text("⚠️ Enter a valid number for N.")
             return PARAM_INPUT
        context.user_data['param_N'] = int(text)
        context.user_data['awaiting_param'] = None
        return await ask_confidence_interval(update)

    # 2. YAMANE FLOW
    if method == 'yamane':
        if context.user_data.get('awaiting_param') == 'yamane_N':
            if not text.isdigit():
                await update.message.reply_text("⚠️ Enter a valid number.")
                return PARAM_INPUT
            context.user_data['param_N'] = int(text)
            
            await update.message.reply_text("Select **Margin of Error (e)**:",
                reply_markup=ReplyKeyboardMarkup([['5% (0.05)', '1% (0.01)'], ['Custom']], one_time_keyboard=True))
            context.user_data['awaiting_param'] = 'yamane_e'
            return PARAM_INPUT
            
        if context.user_data.get('awaiting_param') == 'yamane_e':
            e_val = 0.05
            if '1%' in text: e_val = 0.01
            elif 'Custom' in text:
                 await update.message.reply_text("Enter e (e.g. 0.05):")
                 return PARAM_INPUT
            else:
                try: e_val = float(text)
                except: return PARAM_INPUT
            
            N = context.user_data['param_N']
            result = Sampler.calculate_yamane(N, e_val)
            await display_result(update, result)
            return ConversationHandler.END

    # 3. POWER FLOW
    if method == 'power':
        if 'Small' in text: context.user_data['effect_size'] = 0.2
        elif 'Medium' in text: context.user_data['effect_size'] = 0.5
        elif 'Large' in text: context.user_data['effect_size'] = 0.8
        elif 'Custom' in text:
             await update.message.reply_text("Enter effect size:")
             return PARAM_INPUT
        else:
             try: context.user_data['effect_size'] = float(text)
             except: return PARAM_INPUT
        
        es = context.user_data['effect_size']
        result = Sampler.calculate_power_ttest(effect_size=es)
        await display_result(update, result)
        return ConversationHandler.END

    return PARAM_INPUT

async def ci_select_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if 'Back' in text: return await start_sampling(update, context)
    
    ci = '95%'
    if '99%' in text: ci = '99%'
    if '90%' in text: ci = '90%'
    
    N = context.user_data.get('param_N')
    # Default margin of error 0.05 for Cochran in this simplified flow
    result = Sampler.calculate_cochran(confidence_level=ci, N=N, e=0.05)
    
    await display_result(update, result)
    return ConversationHandler.END

async def display_result(update: Update, result: dict):
    if 'error' in result:
        await update.message.reply_text(f"❌ Error: {result['error']}")
    else:
        # 1. Main Result
        msg = f"✅ **Calculation Result**\n\n"
        msg += f"🔢 **Sample Size (n): {result['sample_size']}**\n\n"
        
        if result.get('total_sample'):
             msg += f"👥 **Total Sample Required:** {result['total_sample']} (split between groups)\n"

        msg += f"📘 **Method:** {result['method']}\n"
        if result.get('population'):
            msg += f"👥 **Population (N):** {result['population']}\n"
        
        # 2. Formula Snippet
        msg += f"\n`{result['formula']}`\n\n"
        
        await update.message.reply_text(msg, parse_mode='Markdown')
        
        # 3. Comprehensive Explanation
        explanation = get_detailed_explanation(result)
        await update.message.reply_text(explanation, parse_mode='Markdown')
        
    await update.message.reply_text(
        "Use /start to Calculate Another or Analyse Data",
        reply_markup=ReplyKeyboardRemove()
    )

def get_detailed_explanation(result: dict) -> str:
    """Generates a comprehensive educational explanation of the result."""
    method = result.get('method', '')
    
    text = "🎓 **Comprehensive Explanation**\n\n"
    
    if "Cochran" in method:
        e = result.get('margin_of_error', 0.05)
        cl = result.get('confidence_level', '95%')
        z_map = {'90%': 1.645, '95%': 1.96, '99%': 2.576}
        z = z_map.get(cl, 1.96)
        
        text += (
            "**1. The Logic:**\n"
            "We used **Cochran's Formula**, which is the gold standard for creating a representative sample "
            "when assessing proportions (percentages) in a population.\n\n"
            "**2. The Components:**\n"
            f"• **Confidence Level ({cl})**: This means if you repeated this study 100 times, "
            f"{cl.replace('%','')} of them would contain the true population value. "
            f"This corresponds to a **Z-score of {z}** in the formula.\n"
            f"• **Margin of Error (e={e})**: This is your precision. You are willing to accept that your result is within "
            f"±{int(e*100)}% of the true value.\n"
            "• **p (0.5)**: We assumed maximum variability (50/50 split), which yields the most conservative (safest) sample size.\n\n"
            "**3. The Calculation:**\n"
            f"We squared the Z-score ({z}² ≈ {z**2:.2f}) and multiplied by variability (0.25). "
            f"Then we divided by the error squared ({e}² = {e**2:.4f}).\n"
        )
        
        if "Finite" in result.get('formula', ''):
            N = result.get('population', 'Unknown')
            text += (
                f"\n**4. Finite Correction:**\n"
                f"Since your population (N={N}) is relatively small, the initial result was adjusted downwards "
                "because you don't need as many people to represent a smaller group."
            )
            
    elif "Yamane" in method:
        N = result.get('population', 'N/A')
        e = result.get('margin_of_error', 0.05)
        
        text += (
            "**1. The Logic:**\n"
            "We used **Taro Yamane's Formula**, a simplified method ideal for finite populations "
            "where the size (N) is known.\n\n"
            "**2. The Components:**\n"
            f"• **Population (N={N})**: The total number of individuals in your study group.\n"
            f"• **Precision (e={e})**: The margin of error (e.g., {int(e*100)}%). This determines how close your sample result will be to the true population value.\n\n"
            "**3. The Calculation:**\n"
            f"The formula `N / (1 + Ne²)` reduces the sample size based on the population limit. "
            f"As N grows larger, this result approaches the standard infinite sample size, but for N={N}, accurately reflects the required count."
        )

    elif "Power" in method:
        es = result.get('effect_size', 0.5)
        
        text += (
            "**1. The Logic:**\n"
            "We used **Power Analysis**, which calculates the sample size needed to statistically detect an effect "
            "if one actually exists. This is crucial for experimental studies to avoid 'Type II Errors' (false negatives).\n\n"
            "**2. The Components:**\n"
            f"• **Effect Size ({es})**: The magnitude of the difference you expect to find. "
            f"{'Small effects require larger samples.' if es < 0.4 else 'Large effects are easier to detect.'}\n"
            "• **Power (0.80)**: The standard 80% probability of finding a significant difference if it exists.\n"
            "• **Alpha (0.05)**: The 5% risk of a 'Type I Error' (false positive).\n\n"
            "**3. Interpretation:**\n"
            "This number ensures your study is scientifically robust. Testing fewer people would mean your results might be inconclusive purely due to lack of data."
        )
        
    else:
        text += "The calculation was performed using standard statistical formulas based on your inputs."

    return text
