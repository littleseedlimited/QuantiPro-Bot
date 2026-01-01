import pandas as pd
import numpy as np
import io
import os
from typing import List, Optional

try:
    import matplotlib
    matplotlib.use('Agg')  # Non-interactive backend
    import matplotlib.pyplot as plt
    import seaborn as sns
    HAS_VISUALS = True
except ImportError:
    HAS_VISUALS = False
    plt = None
    sns = None

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
    def _get_figsize(size_name: str, base_w=10, base_h=6) -> tuple:
        if size_name == 'small': return (base_w * 0.7, base_h * 0.7)
        if size_name == 'large': return (base_w * 1.3, base_h * 1.3)
        return (base_w, base_h)

    @staticmethod
    def _apply_config(config: dict = None):
        """Apply seaborn style and context settings."""
        cfg = config or Visualizer.DEFAULT_CONFIG
        style = cfg.get('style', 'whitegrid')
        context = cfg.get('context', 'notebook')
        sns.set_style(style)
        sns.set_context(context)
        return cfg
    
    @staticmethod
    def _save_plot(filename: str = 'plot.png') -> Optional[str]:
        if not HAS_VISUALS:
            return None
        data_dir = os.getenv("DATA_DIR", "data")
        plots_dir = os.path.join(data_dir, 'plots')
        if not os.path.exists(plots_dir):
             os.makedirs(plots_dir)
        path = os.path.join(plots_dir, filename)
        # Use high DPI for better quality
        plt.savefig(path, bbox_inches='tight', dpi=300)
        plt.close()
        return path

    @staticmethod
    def _setup_figure(title: str, xlabel: str = None, ylabel: str = None, figsize=(12, 8), config: dict = None):
        """Helper to setup plot aesthetics."""
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
             
        plt.title(title, fontsize=16, fontweight='bold', pad=20)
        if xlabel: plt.xlabel(xlabel, fontsize=12)
        if ylabel: plt.ylabel(ylabel, fontsize=12)

    @staticmethod
    def create_table_image(df: pd.DataFrame, title: str = "Data Table", max_rows: int = 20, max_cols: int = 8) -> Optional[str]:
        """Render a DataFrame as a neat table image."""
        if not HAS_VISUALS:
            return None
        
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
        if not HAS_VISUALS:
            return None
        
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
        if not HAS_VISUALS: return None
        Visualizer._setup_figure(f'Distribution of {column}', xlabel=column, ylabel='Frequency', config=config)
        
        palette = config.get('palette', 'viridis') if config else 'viridis'
        # Histplot doesn't take palette directly for single series usually, but we can try color
        color = sns.color_palette(palette)[0] if palette in sns.color_palette() else '#3498db'
            
        sns.histplot(data=df, x=column, kde=True, color=color)
        return Visualizer._save_plot(f'hist_{column}.png')

    @staticmethod
    def create_boxplot(df: pd.DataFrame, x: str, y: str, config: dict = None) -> Optional[str]:
        if not HAS_VISUALS: return None
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
        if not HAS_VISUALS: return None
        Visualizer._setup_figure(f'{y} vs {x}', xlabel=x, ylabel=y, config=config)
        
        palette = config.get('palette', 'deep') if config else 'deep'
        color = sns.color_palette(palette)[0]
        
        sns.scatterplot(data=df, x=x, y=y, color=color, alpha=0.7, s=100)
        return Visualizer._save_plot(f'scatter_{x}_{y}.png')
    
    @staticmethod
    def create_correlation_heatmap(df: pd.DataFrame, columns: List[str] = None, config: dict = None) -> Optional[str]:
        if not HAS_VISUALS: return None
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
        if not HAS_VISUALS: return None
        Visualizer._apply_config(config)
        
        # Determine data size for dynamic plotting
        n_cats = df[x].nunique()
        width = max(10, min(24, n_cats * 0.6))
        
        if config and 'size' in config:
             final_size = Visualizer._get_figsize(config['size'], width, 8)
             plt.figure(figsize=final_size)
        else:
             plt.figure(figsize=(width, 8))
             
        palette = config.get('palette', 'viridis') if config else 'viridis'
        
        if y:
            # Mean bar chart
            chart_data = df.groupby(x)[y].mean().sort_values(ascending=False).reset_index()
            sns.barplot(data=chart_data, x=x, y=y, palette=palette)
            plt.ylabel(f'Mean {y}', fontsize=12)
            title = f'Mean {y} by {x}'
        else:
            # Count bar chart
            chart_data = df[x].value_counts().reset_index()
            chart_data.columns = [x, 'Count']
            sns.barplot(data=chart_data, x=x, y='Count', palette=palette)
            plt.ylabel('Count', fontsize=12)
            title = f'Count by {x}'
            
        plt.title(title, fontsize=16, fontweight='bold', pad=20)
        plt.xlabel(x, fontsize=12)
        
        # Auto-rotate labels if many items or long labels
        plt.xticks(rotation=45, ha='right')
        
        return Visualizer._save_plot(f'bar_{x}_{y or "count"}.png')

    @staticmethod
    def create_line_chart(df: pd.DataFrame, x: str, y: str, config: dict = None) -> Optional[str]:
        if not HAS_VISUALS: return None
        Visualizer._setup_figure(f'{y} over {x}', xlabel=x, ylabel=y, config=config)
        
        palette = config.get('palette', 'deep') if config else 'deep'
        color = sns.color_palette(palette)[0]
        
        plot_df = df.sort_values(x)
        plt.plot(plot_df[x], plot_df[y], marker='o', linewidth=2, markersize=8, color=color)
        plt.fill_between(plot_df[x], plot_df[y], alpha=0.3, color=color)
        
        plt.xticks(rotation=45, ha='right')
        plt.grid(True, alpha=0.3)
        return Visualizer._save_plot(f'line_{x}_{y}.png')

    @staticmethod
    def create_pie_chart(df: pd.DataFrame, column: str, config: dict = None) -> Optional[str]:
        if not HAS_VISUALS: return None
        
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
        
        plt.pie(value_counts, labels=value_counts.index, autopct='%1.1f%%', 
                colors=colors, startangle=90, explode=[0.02]*len(value_counts),
                textprops={'fontsize': 11})
        plt.title(f'Distribution of {column}', fontsize=16, fontweight='bold')
        return Visualizer._save_plot(f'pie_{column}.png')

    @staticmethod
    def create_radar_chart(df: pd.DataFrame, columns: List[str], group_col: str = None, config: dict = None) -> Optional[str]:
        if not HAS_VISUALS or len(columns) < 3: return None
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
        if not HAS_VISUALS: return None
        n_cats = df[x].nunique()
        width = max(10, min(24, n_cats * 0.8))
        Visualizer._setup_figure(f'Distribution of {y} by {x}', xlabel=x, ylabel=y, figsize=(width, 8), config=config)
        
        palette = config.get('palette', 'muted') if config else 'muted'
        sns.violinplot(data=df, x=x, y=y, palette=palette, cut=0)
        plt.xticks(rotation=45, ha='right')
        return Visualizer._save_plot(f'violin_{x}_{y}.png')

    @staticmethod
    def create_pair_plot(df: pd.DataFrame, columns: List[str]) -> Optional[str]:
        if not HAS_VISUALS: return None
        if len(columns) > 5: columns = columns[:5]
        
        # PairPlot handles its own figure
        g = sns.pairplot(df[columns], diag_kind='kde', plot_kws={'alpha': 0.6, 's': 50}, height=2.5)
        g.fig.suptitle('Pair Plot (Scatter Matrix)', y=1.02, fontsize=16, fontweight='bold')
        return Visualizer._save_plot('pair_plot.png')
