
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
    
    # Text states
    title_text = config.get('title', 'Set Title')[:15] + "..." if len(config.get('title', '')) > 15 else config.get('title', 'Set Title')

    text = (f"🎨 **Customize Chart**\n"
            f"Type: `{context.user_data.get('chart_type')}`\n"
            f"Variable: `{context.user_data.get('chart_var')}`\n\n"
            f"**Current Settings:**\n"
            f"• Title: _{config.get('title')}_\n"
            f"• Grid: {grid_state}\n"
            f"• Legend: {legend_state}\n"
            f"• Data Labels: {labels_state}")

    keyboard = [
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
                # Need Y var for line chart usually, assuming simple frequency for now if single var
                # But line chart flow usually has 2 vars. 
                # Let's check how line chart is usually called.
                # In `awaiting_tabulation_visual`, it's single var. `create_line_chart` needs X and Y.
                # If single var, line chart is weird (maybe frequency polygon?). 
                # Visualizer.create_line_chart(df, x, y).
                # The current code in handlers.py passes ONE var: `create_line_chart(df, var)`.
                # Wait, looking at `create_line_chart` signature: `def create_line_chart(df, x, y, ...)`
                # Passing only `var` would fail!
                # The previous handler likely crashed for line chart on single var.
                # I will handle Bar/Pie properly. For Line, I might need to ask for Y or just count.
                # Let's treat Line similar to Bar for single var (Count by X).
                if "Line" in chart_type:
                     # Adapt for single variable line chart (Trend of counts)
                    counts = df[var].value_counts().sort_index().reset_index()
                    counts.columns = [var, 'Count']
                    path = Visualizer.create_line_chart(counts, x=var, y='Count', config=config)
            
            if path:
                await update.message.reply_photo(photo=open(path, 'rb'), caption=f"📊 {config.get('title')}")
                if 'visuals_history' not in context.user_data: 
                    context.user_data['visuals_history'] = []
                context.user_data['visuals_history'].append(path)
                
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
