import pandas as pd
import numpy as np
import io
import os
from typing import List, Optional

try:
    import matplotlib
    matplotlib.use('Agg')  # Non-interactive backend
    HAS_VISUALS = True
except ImportError:
    HAS_VISUALS = False

class Visualizer:
    """
    Visualization Engine for QuantiProBot.
    Generates plots and returns the file path or buffer.
    """
    
    # default config
    DEFAULT_CONFIG = {
        'style': 'whitegrid',
        'palette': 'viridis',
        'figsize': 'medium', # small, medium, large
        'context': 'notebook'
    }

    @staticmethod
    def _get_plt_sns():
        """Lazy load plotting libraries to save memory on startup."""
        if not HAS_VISUALS: return None, None
        import matplotlib.pyplot as plt
        import seaborn as sns
        return plt, sns

    @staticmethod
    def _get_figsize(size_name: str, base_w=10, base_h=6) -> tuple:
        if size_name == 'small': return (base_w * 0.7, base_h * 0.7)
        if size_name == 'large': return (base_w * 1.3, base_h * 1.3)
        return (base_w, base_h)

    @staticmethod
    def _apply_config(config: dict = None):
        """Apply seaborn style and context settings."""
        plt, sns = Visualizer._get_plt_sns()
        if not sns: return config
        
        cfg = config or Visualizer.DEFAULT_CONFIG
        style = cfg.get('style', 'whitegrid')
        context = cfg.get('context', 'notebook')
        sns.set_style(style)
        sns.set_context(context)
        return cfg
    
    @staticmethod
    def _save_plot(filename: str = 'plot.png') -> Optional[str]:
        plt, _ = Visualizer._get_plt_sns()
        if not plt: return None
        
        data_dir = os.getenv("DATA_DIR", "data")
        plots_dir = os.path.join(data_dir, 'plots')
        if not os.path.exists(plots_dir):
             os.makedirs(plots_dir)
        path = os.path.join(plots_dir, filename)
        # Use high DPI for better quality
        plt.savefig(path, bbox_inches='tight', dpi=300)
        plt.close()
        
        # Aggressive GC
        import gc
        gc.collect()
        return path

    @staticmethod
    def _setup_figure(title: str, xlabel: str = None, ylabel: str = None, figsize=(12, 8), config: dict = None):
        """Helper to setup plot aesthetics."""
        plt, _ = Visualizer._get_plt_sns()
        if not plt: return
        
        cfg = Visualizer._apply_config(config)
        
        # Override figsize if 'size' is in config
        if config and 'size' in config:
             # Calculate aspect ratio of requested figsize
             ratio = figsize[1] / figsize[0] if figsize[0] > 0 else 0.6
             base_w = 12
             final_size = Visualizer._get_figsize(config['size'], base_w, base_w * ratio)
             plt.figure(figsize=final_size)
        else:
             plt.figure(figsize=figsize)
             
        plt.title(config.get('title', title), fontsize=16, fontweight='bold', pad=20)
        
        # Axis Labels
        xlabel = config.get('xlabel', xlabel)
        ylabel = config.get('ylabel', ylabel)
        
        if xlabel: plt.xlabel(xlabel, fontsize=12)
        if ylabel: plt.ylabel(ylabel, fontsize=12)
        
        # Gridlines
        if config and config.get('defaults', {}).get('grid', True):
            plt.grid(True, alpha=0.3, linestyle='--')
        elif config and 'grid' in config:
             if config['grid']:
                 plt.grid(True, alpha=0.3, linestyle='--')
             else:
                 plt.grid(False)

    @staticmethod
    def create_table_image(df: pd.DataFrame, title: str = "Data Table", max_rows: int = 20, max_cols: int = 8) -> Optional[str]:
        """Render a DataFrame as a neat table image."""
        plt, _ = Visualizer._get_plt_sns()
        if not plt: return None
        
        # Limit size for readability
        display_df = df.head(max_rows)
        if len(df.columns) > max_cols:
            display_df = display_df.iloc[:, :max_cols]
        
        n_rows, n_cols = display_df.shape
        # Dynamic sizing
        fig_width = max(10, min(24, n_cols * 2.5))
        fig_height = max(5, min(18, n_rows * 0.5 + 2))
        
        fig, ax = plt.subplots(figsize=(fig_width, fig_height))
        ax.axis('off')
        
        table = ax.table(
            cellText=display_df.round(3).values,
            colLabels=display_df.columns,
            cellLoc='center',
            loc='center',
            colColours=['#4a90d9'] * n_cols,
            cellColours=[['#f8f9fa' if i % 2 == 0 else '#ffffff' for _ in range(n_cols)] for i in range(n_rows)]
        )
        
        table.auto_set_font_size(False)
        table.set_fontsize(10)
        table.scale(1.2, 1.8)
        
        for j in range(n_cols):
            table[(0, j)].set_text_props(weight='bold', color='white')
            table[(0, j)].set_height(0.08)
        
        plt.title(title, fontsize=16, fontweight='bold', pad=20)
        
        return Visualizer._save_plot('table_display.png')

    @staticmethod
    def create_stats_table_image(stats_df: pd.DataFrame, title: str = "Descriptive Statistics") -> Optional[str]:
        """Render descriptive statistics as a professional, sleek table image."""
        plt, _ = Visualizer._get_plt_sns()
        if not plt: return None
        
        display_df = stats_df.round(3)
        n_rows, n_cols = display_df.shape
        
        # Constrain sizing to prevent Telegram "Photo_invalid_dimensions" error
        # Telegram has a ~10000px limit, but safer to keep under 4096px
        # At 100 DPI, max 40 inches. We'll keep it much tighter.
        fig_width = max(10, min(18, n_cols * 1.8))  # Max 18 inches
        fig_height = max(4, min(12, n_rows * 0.5 + 2))  # Max 12 inches
        
        # Set background color for a premium feel
        plt.rcParams['figure.facecolor'] = '#fdfdfd'
        fig, ax = plt.subplots(figsize=(fig_width, fig_height), dpi=100)
        ax.axis('off')
        
        # Modern colors
        header_color = '#1a3a5f'  # Deep Navy
        row_colors = ['#f8f9fa', '#ffffff'] # Alternating light grey/white
        edge_color = '#e9ecef'
        
        table = ax.table(
            cellText=display_df.values,
            colLabels=display_df.columns,
            rowLabels=display_df.index,
            cellLoc='center',
            loc='center',
            colColours=[header_color] * n_cols,
            cellColours=[[row_colors[i % 2] for _ in range(n_cols)] for i in range(n_rows)],
            edges='closed'
        )
        
        table.auto_set_font_size(False)
        table.set_fontsize(11)
        table.scale(1.2, 2.2) # Taller rows for readability
        
        # Stylize headers
        for j in range(n_cols):
            cell = table[(0, j)]
            cell.set_text_props(weight='bold', color='white', fontsize=12)
            cell.set_facecolor(header_color)
            cell.set_edgecolor(edge_color)
            
        # Stylize row labels (index)
        for i in range(n_rows):
            cell = table[(i+1, -1)]
            cell.set_text_props(weight='bold', color='#333333')
            cell.set_facecolor('#eef2f7')
            cell.set_edgecolor(edge_color)
            cell.set_width(0.15) # Ensure index doesn't wrap too aggressively

        # Stylize data cells
        for i in range(n_rows):
            for j in range(n_cols):
                cell = table[(i+1, j)]
                cell.set_edgecolor(edge_color)
                cell.set_text_props(color='#444444')

        plt.title(title, fontsize=20, fontweight='bold', color='#1a3a5f', pad=30)
        
        # Clean up global state
        path = Visualizer._save_plot('stats_table.png')
        plt.close(fig)
        return path

    @staticmethod
    def create_histogram(df: pd.DataFrame, column: str, config: dict = None) -> Optional[str]:
        plt, sns = Visualizer._get_plt_sns()
        if not plt: return None
        Visualizer._setup_figure(f'Distribution of {column}', xlabel=column, ylabel='Frequency', config=config)
        
        palette = config.get('palette', 'viridis') if config else 'viridis'
        # Histplot doesn't take palette directly for single series usually, but we can try color
        color = sns.color_palette(palette)[0] if palette in sns.color_palette() else '#3498db'
            
        sns.histplot(data=df, x=column, kde=True, color=color)
        return Visualizer._save_plot(f'hist_{column}.png')

    @staticmethod
    def create_boxplot(df: pd.DataFrame, x: str, y: str, config: dict = None) -> Optional[str]:
        plt, sns = Visualizer._get_plt_sns()
        if not plt: return None
        # Dynamic width for many categories
        n_cats = df[x].nunique()
        width = max(10, min(24, n_cats * 0.8))
        Visualizer._setup_figure(f'{y} by {x}', xlabel=x, ylabel=y, figsize=(width, 8), config=config)
        
        palette = config.get('palette', 'Set2') if config else 'Set2'
        sns.boxplot(data=df, x=x, y=y, palette=palette)
        # Rotate labels if many categories
        if n_cats > 5:
            plt.xticks(rotation=45, ha='right')
        return Visualizer._save_plot(f'box_{x}_{y}.png')

    @staticmethod
    def create_scatterplot(df: pd.DataFrame, x: str, y: str, config: dict = None) -> Optional[str]:
        plt, sns = Visualizer._get_plt_sns()
        if not plt: return None
        Visualizer._setup_figure(f'{y} vs {x}', xlabel=x, ylabel=y, config=config)
        
        palette = config.get('palette', 'deep') if config else 'deep'
        color = sns.color_palette(palette)[0]
        
        sns.scatterplot(data=df, x=x, y=y, color=color, alpha=0.7, s=100)
        return Visualizer._save_plot(f'scatter_{x}_{y}.png')
    
    @staticmethod
    def create_correlation_heatmap(df: pd.DataFrame, columns: List[str] = None, config: dict = None) -> Optional[str]:
        plt, sns = Visualizer._get_plt_sns()
        if not plt: return None
        Visualizer._apply_config(config)
        
        if columns:
            corr = df[columns].corr()
        else:
            corr = df.select_dtypes(include=['number']).corr()
        
        # Dynamic size based on matrix size
        n = len(corr)
        size = max(10, min(24, n * 1.2))
        
        # Override if config size present
        if config and 'size' in config:
             size_tuple = Visualizer._get_figsize(config['size'], size, size * 0.8)
             plt.figure(figsize=size_tuple)
        else:
             plt.figure(figsize=(size, size * 0.8))
        
        cmap = config.get('palette', 'coolwarm') if config else 'coolwarm'
        # If palette is categorical (like Set2), revert to coolwarm for heatmap
        if cmap in ['Set1', 'Set2', 'Set3', 'Pastel1', 'Dark2']:
            cmap = 'coolwarm'
            
        sns.heatmap(corr, annot=True, cmap=cmap, fmt=".2f", 
                   linewidths=0.5, annot_kws={"size": 10 if n < 10 else 8})
        plt.title('Correlation Matrix', fontsize=16, fontweight='bold', pad=20)
        plt.xticks(rotation=45, ha='right')
        plt.yticks(rotation=0)
        return Visualizer._save_plot('correlation_matrix.png')

    @staticmethod
    def create_bar_chart(df: pd.DataFrame, x: str, y: str = None, config: dict = None) -> Optional[str]:
        """Create a bar chart with auto-rotation and sorting."""
        plt, sns = Visualizer._get_plt_sns()
        if not plt: return None
        Visualizer._apply_config(config)
        return Visualizer._save_plot(f'bar_{x}_{y or "count"}.png')

    @staticmethod
    def create_crosstab_heatmap(df: pd.DataFrame, row: str, col: str, config: dict = None) -> Optional[str]:
        """Create a styled heatmap/table for crosstabs."""
        plt, sns = Visualizer._get_plt_sns()
        if not plt: return None
        
        # Calculate Crosstab
        ct = pd.crosstab(df[row], df[col])
        
        # Figure setup
        config = config or {}
        Visualizer._setup_figure(f'{row} x {col}', xlabel=col, ylabel=row, config=config)
        
        # Heatmap
        palette = config.get('palette', 'YlGnBu')  # Heatmap friendly default
        sns.heatmap(ct, annot=True, fmt='d', cmap=palette, cbar=False, 
                   annot_kws={'size': 12, 'weight': 'bold'})
        
        plt.title(f'Crosstabulation: {row} vs {col}', fontsize=14, pad=20)
        plt.xticks(rotation=45)
        plt.yticks(rotation=0)
        
        return Visualizer._save_plot(f'crosstab_{row}_{col}.png')

    @staticmethod
    def create_bar_chart(df: pd.DataFrame, x: str, y: str = None, config: dict = None) -> Optional[str]:
        plt, sns = Visualizer._get_plt_sns()
        if not plt: return None
        
        config = config or {}
        orientation = config.get('orientation', 'v') # v or h
        
        # Determine data size
        n_cats = df[x].nunique()
        base_w = max(10, min(24, n_cats * 0.6))
        
        if config and 'size' in config:
             final_size = Visualizer._get_figsize(config['size'], base_w, 8)
             plt.figure(figsize=final_size)
        else:
             plt.figure(figsize=(base_w, 8))
             
        palette = config.get('palette', 'viridis')
        
        # Prepare Data
        if y:
            # Mean bar chart
            chart_data = df.groupby(x)[y].mean().sort_values(ascending=False).reset_index()
            val_col = y
            cat_col = x
            lbl = f'Mean {y}'
            title = f'Mean {y} by {x}'
        else:
            # Count bar chart
            chart_data = df[x].value_counts().reset_index()
            chart_data.columns = [x, 'Count']
            val_col = 'Count'
            cat_col = x
            lbl = 'Count'
            title = f'Count by {x}'

        # Plot based on orientation
        if orientation == 'h':
            # Swap x/y
            ax = sns.barplot(data=chart_data, x=val_col, y=cat_col, palette=palette)
            plt.xlabel(lbl)
            plt.ylabel(cat_col)
        else:
            ax = sns.barplot(data=chart_data, x=cat_col, y=val_col, palette=palette)
            plt.ylabel(lbl)
            plt.xlabel(cat_col)
            plt.xticks(rotation=45, ha='right')

        # Custom Title/Labels
        plt.title(config.get('title', title), fontsize=16, fontweight='bold', pad=20)
        if config.get('xlabel'): plt.xlabel(config['xlabel'])
        if config.get('ylabel'): plt.ylabel(config['ylabel'])
        
        
        # Data Labels & Axis Cleaning
        if config.get('data_labels', False):
            label_pos = config.get('label_pos', 'edge')
            
            # Map user friendly pos to matplotlib arg
            # 'edge' is standard. 'center' is standard. 'base' is not direct.
            mpl_pos = 'center' if label_pos == 'center' else 'edge'
            color = 'white' if label_pos == 'center' else 'black'
            
            for container in ax.containers:
                ax.bar_label(container, fmt='%.2f' if y else '%d', padding=3, label_type=mpl_pos, color=color, fontweight='bold')
            
            # Use requested: "If data label is selected, then remove Y-axis" (or value axis)
            if orientation == 'h':
                ax.get_xaxis().set_visible(False) # Value axis is X for horizontal
                sns.despine(left=True, bottom=True)
            else:
                ax.get_yaxis().set_visible(False) # Value axis is Y for vertical
                sns.despine(left=True, bottom=True)
        else:
            # Standard grid/spine
             if config.get('grid', False):
                 axis = 'x' if orientation == 'h' else 'y'
                 plt.grid(True, axis=axis, alpha=0.3)

        return Visualizer._save_plot(f'bar_{x}_{y or "count"}.png')

    @staticmethod
    def create_line_chart(df: pd.DataFrame, x: str, y: str, config: dict = None) -> Optional[str]:
        plt, sns = Visualizer._get_plt_sns()
        if not plt: return None
        Visualizer._setup_figure(f'{y} over {x}', xlabel=x, ylabel=y, config=config)
        
        palette = config.get('palette', 'deep') if config else 'deep'
        color = sns.color_palette(palette)[0]
        
        plot_df = df.sort_values(x)
        plt.plot(plot_df[x], plot_df[y], marker='o', linewidth=2, markersize=8, color=color)
        plt.fill_between(plot_df[x], plot_df[y], alpha=0.3, color=color)
        
        # Options: Data Labels
        if config and config.get('data_labels', False):
             for i, txt in enumerate(plot_df[y]):
                 plt.annotate(f"{txt:.2f}", (plot_df[x].iloc[i], plot_df[y].iloc[i]), 
                              textcoords="offset points", xytext=(0,10), ha='center')

        plt.xticks(rotation=45, ha='right')
        
        # Grid handled by _setup_figure
        
        return Visualizer._save_plot(f'line_{x}_{y}.png')

    @staticmethod
    def create_pie_chart(df: pd.DataFrame, column: str, config: dict = None) -> Optional[str]:
        plt, sns = Visualizer._get_plt_sns()
        if not plt: return None
        
        if config and 'size' in config:
             size = Visualizer._get_figsize(config['size'], 12, 10)
             plt.figure(figsize=size)
        else:
             plt.figure(figsize=(12, 10))
        
        value_counts = df[column].value_counts()
        
        # Group small slices into "Other" if too many
        if len(value_counts) > 10:
            main = value_counts[:9]
            other = pd.Series([value_counts[9:].sum()], index=['Other'])
            value_counts = pd.concat([main, other])
            
        palette = config.get('palette', 'Pastel1') if config else 'Pastel1'
        # Pie requires a list of colors
        colors = sns.color_palette(palette, len(value_counts))
        
        # Options: Data Labels
        autopct = '%1.1f%%' if (config is None or config.get('data_labels', True)) else None
        
        plt.pie(value_counts, labels=value_counts.index, autopct=autopct, 
                colors=colors, startangle=90, explode=[0.02]*len(value_counts),
                textprops={'fontsize': 11})
        
        title_text = config.get('title', f'Distribution of {column}') if config else f'Distribution of {column}'
        plt.title(title_text, fontsize=16, fontweight='bold')
        
        if config and config.get('legend', True):
             plt.legend(bbox_to_anchor=(1, 1))

        return Visualizer._save_plot(f'pie_{column}.png')

    @staticmethod
    def create_histogram(df: pd.DataFrame, column: str, config: dict = None) -> Optional[str]:
        """Create a histogram for numeric distribution."""
        plt, sns = Visualizer._get_plt_sns()
        if not plt: return None
        
        Visualizer._setup_figure(f'Distribution of {column}', xlabel=column, ylabel='Frequency', config=config)
        
        palette = config.get('palette', 'muted') if config else 'muted'
        color = sns.color_palette(palette)[0]
        
        # Plot
        sns.histplot(data=df, x=column, kde=True, color=color, alpha=0.6)
        
        # Options: Data Labels (for bins - tricky on hist, maybe skip or add counts to largest bins?)
        # For histograms, standard usage is just axis labels.
        # We can annotate the mean/median line if requested?
        # For now, keep it simple.
        
        mean_val = df[column].mean()
        plt.axvline(mean_val, color='red', linestyle='--', label=f'Mean: {mean_val:.2f}')
        if config and config.get('legend', True):
             plt.legend()
             
        return Visualizer._save_plot(f'hist_{column}.png')

    @staticmethod
    def create_radar_chart(df: pd.DataFrame, columns: List[str], group_col: str = None, config: dict = None) -> Optional[str]:
        plt, sns = Visualizer._get_plt_sns()
        if not plt or len(columns) < 3: return None
        Visualizer._apply_config(config)
        
        fig, ax = plt.subplots(figsize=(10, 10), subplot_kw=dict(polar=True))
        
        num_vars = len(columns)
        angles = np.linspace(0, 2 * np.pi, num_vars, endpoint=False).tolist()
        angles += angles[:1]
        
        palette = config.get('palette', 'Set1') if config else 'Set1'
        colors_list = sns.color_palette(palette)
        
        if group_col and group_col in df.columns:
            groups = df[group_col].unique()[:5]
            # Cycle through colors if more groups than colors
            
            for idx, group in enumerate(groups):
                values = df[df[group_col] == group][columns].mean().tolist()
                values += values[:1]
                color = colors_list[idx % len(colors_list)]
                ax.plot(angles, values, 'o-', linewidth=2, label=str(group), color=color)
                ax.fill(angles, values, alpha=0.15, color=color)
            plt.legend(loc='upper right', bbox_to_anchor=(1.3, 1.0))
        else:
            values = df[columns].mean().tolist()
            values += values[:1]
            color = colors_list[0]
            ax.plot(angles, values, 'o-', linewidth=2, color=color)
            ax.fill(angles, values, alpha=0.25, color=color)
        
        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(columns, fontsize=10)
        # Pad title to avoid overlap
        plt.title('Multi-Variable Comparison (Radar)', fontsize=16, fontweight='bold', y=1.1)
        return Visualizer._save_plot('radar_chart.png')

    @staticmethod
    def create_violin_plot(df: pd.DataFrame, x: str, y: str, config: dict = None) -> Optional[str]:
        plt, sns = Visualizer._get_plt_sns()
        if not plt: return None
        n_cats = df[x].nunique()
        width = max(10, min(24, n_cats * 0.8))
        Visualizer._setup_figure(f'Distribution of {y} by {x}', xlabel=x, ylabel=y, figsize=(width, 8), config=config)
        
        palette = config.get('palette', 'muted') if config else 'muted'
        sns.violinplot(data=df, x=x, y=y, palette=palette, cut=0)
        plt.xticks(rotation=45, ha='right')
        return Visualizer._save_plot(f'violin_{x}_{y}.png')

    @staticmethod
    def create_stats_table_image(stats_df: pd.DataFrame, title: str = "Descriptive Statistics") -> Optional[str]:
        """Render a dataframe as a static image table."""
        plt, sns = Visualizer._get_plt_sns()
        if not plt: return None
        
        try:
            # Calculate size based on rows/cols
            rows, cols = stats_df.shape
            w = max(8, cols * 1.5)
            h = max(4, rows * 0.5 + 2)
            
            fig, ax = plt.subplots(figsize=(w, h))
            ax.axis('off')
            
            # Create table
            table = plt.table(cellText=stats_df.round(3).values,
                              colLabels=stats_df.columns,
                              rowLabels=stats_df.index,
                              cellLoc='center',
                              loc='center',
                              bbox=[0, 0, 1, 0.9])
            
            table.auto_set_font_size(False)
            table.set_fontsize(11)
            table.scale(1.2, 1.2)
            
            plt.title(title, fontsize=16, fontweight='bold', y=0.95)
            
            path = Visualizer._save_plot("stats_table.png")
            return path
        except Exception as e:
            print(f"Stats table error: {e}")
            return None

    @staticmethod
    def create_pair_plot(df: pd.DataFrame, columns: List[str]) -> Optional[str]:
        plt, sns = Visualizer._get_plt_sns()
        if not plt: return None
        if len(columns) > 5: columns = columns[:5]
        
        # PairPlot handles its own figure
        g = sns.pairplot(df[columns], diag_kind='kde', plot_kws={'alpha': 0.6, 's': 50}, height=2.5)
        g.fig.suptitle('Pair Plot (Scatter Matrix)', y=1.02, fontsize=16, fontweight='bold')
        return Visualizer._save_plot('pair_plot.png')
