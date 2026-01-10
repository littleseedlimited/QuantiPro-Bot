from src.utils.logger import logger
import pandas as pd
import numpy as np
from typing import Dict, List, Any, Union

# Optional Dependencies (Lazy Loaded)
HAS_ADVANCED_STATS = True # Assumed true if installed, checks inside methods

class Analyzer:
    """
    Statistical Analysis Engine for QuantiProBot.
    Wraps pandas, scipy, statsmodels, and pingouin.
    """

    @staticmethod
    def get_descriptive_stats(df: pd.DataFrame, columns: List[str] = None) -> pd.DataFrame:
        """
        Calculate comprehensive descriptive statistics.
        Includes: N, Mean, Median, Mode, Std Dev, MAD, Variance, Min, Max, Range, Sum, Skewness, Kurtosis.
        """
        if columns:
            target_df = df[columns].apply(pd.to_numeric, errors='coerce')
        else:
            target_df = df.select_dtypes(include=[np.number])
        
        # Drop completely empty columns
        target_df = target_df.dropna(axis=1, how='all')
        
        if target_df.empty:
             return pd.DataFrame()

        # Build comprehensive stats
        stats_dict = {}
        for col in target_df.columns:
            col_data = target_df[col].dropna()
            if len(col_data) == 0:
                continue
            
            mode_result = col_data.mode()
            mode_val = mode_result.iloc[0] if len(mode_result) > 0 else np.nan
            
            stats_dict[col] = {
                'N': len(col_data),
                'Mean': col_data.mean(),
                'Median': col_data.median(),
                'Mode': mode_val,
                'Std Dev': col_data.std(),
                'MAD': (col_data - col_data.mean()).abs().mean(),  # Mean Absolute Deviation
                'Variance': col_data.var(),
                'Min': col_data.min(),
                'Max': col_data.max(),
                'Range': col_data.max() - col_data.min(),
                'Sum': col_data.sum(),
                'Skewness': col_data.skew(),
                'Kurtosis': col_data.kurt()
            }
        
        desc = pd.DataFrame(stats_dict).T
        return desc

    @staticmethod
    def get_correlation(df: pd.DataFrame, columns: List[str] = None, method: str = 'pearson') -> Dict[str, Any]:
        """
        Calculate correlation matrix with p-values and significance stars.
        Returns a dictionary with r-values, p-values, and stars.
        """
        if columns:
            target_df = df[columns].apply(pd.to_numeric, errors='coerce')
        else:
            target_df = df.select_dtypes(include=[np.number])

        # Drop columns that are entirely NaN
        target_df = target_df.dropna(axis=1, how='all')

        if target_df.shape[1] < 2:
            return {"error": "Need at least 2 numeric columns for correlation."}

        from scipy.stats import pearsonr, spearmanr, kendalltau
        
        corr_matrix = target_df.corr(method=method)
        p_matrix = pd.DataFrame(np.zeros((target_df.shape[1], target_df.shape[1])), 
                               index=target_df.columns, columns=target_df.columns)
        star_matrix = pd.DataFrame(np.empty((target_df.shape[1], target_df.shape[1]), dtype=str), 
                                  index=target_df.columns, columns=target_df.columns)

        for i in range(len(target_df.columns)):
            for j in range(len(target_df.columns)):
                if i == j:
                    p_matrix.iloc[i, j] = 0.0
                    star_matrix.iloc[i, j] = ""
                    continue
                
                # Drop NaNs pairwise for better reliability
                valid_data = target_df.iloc[:, [i, j]].dropna()
                if len(valid_data) < 3:
                     p_matrix.iloc[i, j] = 1.0
                     star_matrix.iloc[i, j] = ""
                     continue

                if method == 'pearson':
                    from scipy.stats import pearsonr
                    r, p = pearsonr(valid_data.iloc[:, 0], valid_data.iloc[:, 1])
                elif method == 'spearman':
                    from scipy.stats import spearmanr
                    r, p = spearmanr(valid_data.iloc[:, 0], valid_data.iloc[:, 1])
                else: # kendall
                    from scipy.stats import kendalltau
                    r, p = kendalltau(valid_data.iloc[:, 0], valid_data.iloc[:, 1])
                
                p_matrix.iloc[i, j] = p
                
                # Significance stars
                if p < 0.001: stars = "***"
                elif p < 0.01: stars = "**"
                elif p < 0.05: stars = "*"
                else: stars = ""
                star_matrix.iloc[i, j] = stars

        return {
            "r_values": corr_matrix,
            "p_values": p_matrix,
            "stars": star_matrix,
            "method": method.title()
        }

    @staticmethod
    def run_ttest(df: pd.DataFrame, group_col: str, value_col: str, paired: bool = False) -> Dict[str, Any]:
        """
        Run T-test (Independent or Paired).
        """
        if not HAS_ADVANCED_STATS:
            return {"error": "Advanced statistics libraries (pingouin/scipy) are not installed."}

        # Data Cleaning: Convert to numeric, coercion errors to NaN
        df[value_col] = pd.to_numeric(df[value_col], errors='coerce')
        clean_df = df[[group_col, value_col]].dropna()

        groups = clean_df[group_col].unique()
        if len(groups) != 2:
            return {
                "error": f"T-Test requires exactly 2 groups. Found {len(groups)} groups: {list(groups)[:5]}. Check your data cleaning."
            }
            
        g1 = clean_df[clean_df[group_col] == groups[0]][value_col]
        g2 = clean_df[clean_df[group_col] == groups[1]][value_col]
        
        import pingouin as pg
        res = pg.ttest(g1, g2, paired=paired)
        
        return {
            "test": "Paired T-test" if paired else "Independent T-test",
            "groups": {str(groups[0]): g1.mean(), str(groups[1]): g2.mean()},
            "t_val": res['T'].values[0],
            "p_val": res['p-val'].values[0],
            "dof": res['dof'].values[0],
            "cohen_d": res['cohen-d'].values[0] if 'cohen-d' in res else None,
            "power": res['power'].values[0] if 'power' in res else None,
            "full_result": res
        }

    @staticmethod
    def run_anova(df: pd.DataFrame, dv: str, between: str) -> pd.DataFrame:
        """
        One-way ANOVA.
        """
        if not HAS_ADVANCED_STATS:
            return pd.DataFrame() # Empty if no libs

        import pingouin as pg
        aov = pg.anova(data=df, dv=dv, between=between)
        return aov

    @staticmethod
    def run_regression(df: pd.DataFrame, x_cols: List[str], y_col: str) -> Dict[str, Any]:
        """
        Run Multiple Regression (Simple, Multiple, or Binary Logistic).
        Automatically encodes categorical variables.
        """
        if not HAS_ADVANCED_STATS:
            return {"error": "Statsmodels is not installed."}

        # Work with a copy
        work_df = df[x_cols + [y_col]].copy()
        
        # Drop rows with all NaN
        work_df = work_df.dropna(how='all')
        
        if work_df.empty:
            return {"error": "No valid data points available."}
        
        # Encode categorical variables
        encoded_info = []
        for col in x_cols + [y_col]:
            if work_df[col].dtype == 'object' or str(work_df[col].dtype) == 'category':
                # Label encode categorical variables
                from sklearn.preprocessing import LabelEncoder
                le = LabelEncoder()
                # Fill NaN with placeholder before encoding
                work_df[col] = work_df[col].fillna('_missing_')
                work_df[col] = le.fit_transform(work_df[col].astype(str))
                encoded_info.append(f"{col}: {dict(zip(le.classes_, le.transform(le.classes_)))}")
            else:
                # Try to convert to numeric
                work_df[col] = pd.to_numeric(work_df[col], errors='coerce')
        
        # Drop remaining NaN after encoding
        clean_df = work_df.dropna()
        
        if clean_df.empty or len(clean_df) < 3:
            return {"error": f"Insufficient data after encoding. Need at least 3 valid rows, got {len(clean_df)}."}

        X = clean_df[x_cols]
        y = clean_df[y_col]
        
        import statsmodels.api as sm
        X = sm.add_constant(X)
        
        try:
            # Decide OLS vs Logit
            unique_y = y.dropna().unique()
            if len(unique_y) == 2:
                # Logistic
                model = sm.Logit(y, X).fit(disp=0)
                res_type = "Binary Logistic Regression"
            else:
                # OLS
                model = sm.OLS(y, X).fit()
                res_type = "Multiple Linear Regression"
            
            result = {
                "test_type": res_type,
                "r_squared": model.rsquared if hasattr(model, 'rsquared') else getattr(model, 'prsquared', 0),
                "f_pvalue": getattr(model, 'f_pvalue', 0),
                "params": model.params.to_dict(),
                "pvalues": model.pvalues.to_dict(),
                "summary": model.summary().as_text(),
                "n_observations": len(clean_df)
            }
            
            if encoded_info:
                result["encoding_note"] = "Categorical variables were label-encoded: " + ", ".join(encoded_info[:3])
            
            return result
        except Exception as e:
            logger.error(f"Regression failed: {e}")
            return {"error": f"Regression calculation error: {str(e)}"}



    @staticmethod
    def run_cronbach_alpha(df: pd.DataFrame, columns: List[str]) -> Dict[str, Any]:
        """
        Calculate Cronbach's Alpha reliability.
        """
        if not HAS_ADVANCED_STATS:
            return {"error": "Pingouin required for Cronbach Alpha."}
            
        import pingouin as pg
        alpha = pg.cronbach_alpha(data=df[columns])
        return {
            "alpha": alpha[0],
            "conf_interval": alpha[1],
            "interpretation": "Excellent" if alpha[0] > 0.9 else "Good" if alpha[0] > 0.8 else "Acceptable" if alpha[0] > 0.7 else "Poor"
        }

    @staticmethod
    def run_chi2(df: pd.DataFrame, col1: str, col2: str) -> Dict[str, Any]:
        """
        Chi-square test of independence.
        """
        if not HAS_ADVANCED_STATS:
            return {"error": "Scipy required for Chi-square."}
            
        contingency = pd.crosstab(df[col1], df[col2])
        from scipy import stats
        chi2, p, dof, expected = stats.chi2_contingency(contingency)
        
        return {
            "chi2": chi2,
            "p_val": p,
            "dof": dof,
            "contingency_table": contingency.to_dict()
        }

    @staticmethod
    def run_non_parametric(df: pd.DataFrame, group_col: str, value_col: str, test: str = 'mann-whitney') -> Dict[str, Any]:
        """
        Run Mann-Whitney U or Wilcoxon.
        """
        if not HAS_ADVANCED_STATS:
            return {"error": "Pingouin/Scipy required."}
            
        groups = df[group_col].dropna().unique()
        if len(groups) != 2:
            return {"error": f"Required 2 groups, found {len(groups)}."}

        g1 = df[df[group_col] == groups[0]][value_col]
        g2 = df[df[group_col] == groups[1]][value_col]
        
        import pingouin as pg
        if test == 'mann-whitney':
            res = pg.mwu(g1, g2)
        else: # wilcoxon
            res = pg.wilcoxon(g1, g2)
            
        return res.to_dict(orient='records')[0]

    @staticmethod
    def run_logistic_regression(df: pd.DataFrame, x_cols: List[str], y_col: str) -> Dict[str, Any]:
        """
        Binary Logistic Regression.
        """
        if not HAS_ADVANCED_STATS:
            return {"error": "Statsmodels required."}
            
        clean_df = df[[y_col] + x_cols].dropna()
        X = clean_df[x_cols]
        y = clean_df[y_col]
        X = sm.add_constant(X)
        
        model = sm.Logit(y, X).fit()
        
        return {
            "summary": model.summary().as_text(),
            "params": model.params.to_dict(),
            "pvalues": model.pvalues.to_dict(),
            "pseudo_r2": model.prsquared
        }

    @staticmethod
    def frequency_table(df: pd.DataFrame, column: str) -> Dict[str, Any]:
        """
        Create a frequency table (tabulation) for a single variable.
        Returns counts and percentages.
        """
        try:
            freq = df[column].value_counts(dropna=False)
            pct = df[column].value_counts(normalize=True, dropna=False) * 100
            
            result_df = pd.DataFrame({
                'Count': freq,
                'Percent': pct.round(2),
                'Cumulative %': pct.cumsum().round(2)
            })
            
            # Add total row
            total_row = pd.DataFrame({
                'Count': [freq.sum()],
                'Percent': [100.0],
                'Cumulative %': [100.0]
            }, index=['TOTAL'])
            
            result_df = pd.concat([result_df, total_row])
            
            return {
                "table": result_df,
                "n_categories": len(freq),
                "n_observations": freq.sum(),
                "mode": freq.idxmax() if not freq.empty else None
            }
        except Exception as e:
            return {"error": str(e)}

    @staticmethod
    def crosstab(df: pd.DataFrame, row_var: str, col_var: str, 
                 show_row_pct: bool = False, show_col_pct: bool = False,
                 show_total_pct: bool = False) -> Dict[str, Any]:
        """
        Create a crosstabulation (contingency table) for two variables.
        
        Options:
        - show_row_pct: Show row percentages
        - show_col_pct: Show column percentages
        - show_total_pct: Show total percentages
        """
        try:
            # Main crosstab with counts (margins included for calculation but validation needed)
            ct = pd.crosstab(df[row_var], df[col_var], margins=True, margins_name='Total')
            
            # Store full table including totals
            full_counts = ct.copy()
            
            # Remove margins for the main display loop to avoid 'Total' key errors during iteration
            # if the caller is iterating over unique values of the variable
            if 'Total' in ct.index:
                ct = ct.drop('Total', axis=0)
            if 'Total' in ct.columns:
                ct = ct.drop('Total', axis=1)
            
            result = {
                "counts": ct,
                "full_counts": full_counts, # Keep full counts if needed
                "row_var": row_var,
                "col_var": col_var,
                "n_rows": len(df[row_var].unique()),
                "n_cols": len(df[col_var].unique()),
                "n_observations": len(df)
            }
            
            # Row percentages
            if show_row_pct:
                row_pct = pd.crosstab(df[row_var], df[col_var], normalize='index', 
                                      margins=True, margins_name='Total') * 100
                if 'Total' in row_pct.index: row_pct = row_pct.drop('Total', axis=0)
                if 'Total' in row_pct.columns: row_pct = row_pct.drop('Total', axis=1)
                result["row_percentages"] = row_pct.round(2)
            
            # Column percentages
            if show_col_pct:
                col_pct = pd.crosstab(df[row_var], df[col_var], normalize='columns',
                                      margins=True, margins_name='Total') * 100
                if 'Total' in col_pct.index: col_pct = col_pct.drop('Total', axis=0)
                if 'Total' in col_pct.columns: col_pct = col_pct.drop('Total', axis=1)
                result["col_percentages"] = col_pct.round(2)
            
            # Total percentages
            if show_total_pct:
                total_pct = pd.crosstab(df[row_var], df[col_var], normalize='all',
                                        margins=True, margins_name='Total') * 100
                if 'Total' in total_pct.index: total_pct = total_pct.drop('Total', axis=0)
                if 'Total' in total_pct.columns: total_pct = total_pct.drop('Total', axis=1)
                result["total_percentages"] = total_pct.round(2)
            
            return result
        except Exception as e:
            logger.error(f"Crosstab error: {str(e)}", exc_info=True)
            return {"error": str(e)}

    @staticmethod
    def format_crosstab_mobile(ct_result: Dict[str, Any]) -> str:
        """
        Format crosstab for mobile-friendly display using markdown tables.
        """
        if "error" in ct_result:
            return f"❌ **Crosstab Error:** {ct_result['error']}"
        
        counts = ct_result["counts"]
        row_var = ct_result.get('row_var', 'Row')
        col_var = ct_result.get('col_var', 'Col')
        
        output = f"🎯 **Crosstab: {row_var} × {col_var}**\n"
        output += f"📏 N={ct_result.get('n_observations', 'N/A')}\n\n"
        
        # Determine what to show (Counts is default)
        # For simplicity in chat, we prioritize Counts or Row %
        
        # Build Markdown Table
        try:
            # Header
            cols = [str(c)[:8] for c in counts.columns]
            header = f"| {row_var[:10]} | " + " | ".join(cols) + " |"
            sep = "|---|" + "|".join(["---"] * len(cols)) + "|"
            
            output += "```\n"
            output += header + "\n"
            output += sep + "\n"
            
            for idx, row in counts.iterrows():
                row_label = str(idx)[:10]
                row_vals = []
                for col_name in counts.columns:
                    val = row[col_name]
                    # If percentages exist, maybe append them? 
                    # For now just counts to keep it clean, user can export for more
                    row_vals.append(str(val))
                
                output += f"| {row_label} | " + " | ".join(row_vals) + " |\n"
            
            output += "```\n"

            # Add percentages summary if requested/available
            output += "\n*Detailed percentages available in export.*"
                
        except Exception as e:
            output += f"\n(Table Error: {e})"
            
        return output

    @staticmethod
    def format_stats_mobile(desc_df: pd.DataFrame) -> str:
        """
        Format comprehensive descriptive statistics in a tabular view.
        Uses tabulate for a clean, code-block presentation.
        """
        if desc_df.empty:
            return "No numeric data available."
        
        try:
            from tabulate import tabulate
            # Round for display and truncate names
            display_df = desc_df.copy()
            display_df.index = [str(i)[:25] + '..' if len(str(i)) > 25 else str(i) for i in display_df.index]
            
            # Create the table with clean float formatting
            table = tabulate(display_df, headers='keys', tablefmt='psql', floatfmt=".3f")
            return f"📊 **Comprehensive Descriptive Statistics**\n\n```\n{table}\n```"
        except ImportError:
            # Fallback to pandas to_string
            table = desc_df.to_string(float_format="{:.3f}".format)
            return f"📊 **Comprehensive Descriptive Statistics**\n\n```\n{table}\n```"
        except Exception as e:
            return f"Error formatting stats: {str(e)}"
