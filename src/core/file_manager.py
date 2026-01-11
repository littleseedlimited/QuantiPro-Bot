import pandas as pd
import json
import os
import logging
from typing import Tuple, Dict, Any, Optional, List

try:
    import pyreadstat
except ImportError:
    pyreadstat = None

logger = logging.getLogger(__name__)

class FileManager:
    """
    Universal File Manager for QuantiBot.
    Handles loading of CSV, Excel, SPSS, Stata, SAS, JSON, Parquet, etc.
    """

    @staticmethod
    def identify_format(file_path: str) -> str:
        """Detect file format based on extension."""
        _, ext = os.path.splitext(file_path)
        return ext.lower().replace('.', '')

    @staticmethod
    def get_active_dataframe(file_path: str) -> Optional[pd.DataFrame]:
        """Safe reload of a dataframe from a known path."""
        if not file_path or not os.path.exists(file_path):
            return None
        try:
            df, _ = FileManager.load_file(file_path)
            return FileManager.clean_data(df)
        except Exception as e:
            logger.error(f"Failed to reload active dataframe: {e}")
            return None

    @staticmethod
    def load_file(file_path: str, file_format: str = None) -> Tuple[Optional[pd.DataFrame], Dict[str, Any]]:
        """
        Load a file into a pandas DataFrame.
        Returns: (DataFrame, Metadata Dictionary)
        """
        if not file_format:
            file_format = FileManager.identify_format(file_path)

        try:
            if file_format in ['csv', 'txt', 'tsv']:
                return FileManager._load_csv(file_path)
            elif file_format in ['xlsx', 'xls']:
                return FileManager._load_excel(file_path)
            elif file_format == 'sav':
                return FileManager._load_spss(file_path)
            elif file_format == 'dta':
                return FileManager._load_stata(file_path)
            elif file_format == 'json':
                return FileManager._load_json(file_path)
            elif file_format == 'parquet':
                return FileManager._load_parquet(file_path)
            else:
                raise ValueError(f"Unsupported file format: {file_format}")
        except Exception as e:
            logger.error(f"Error loading file {file_path}: {str(e)}")
            raise e

    @staticmethod
    def _load_csv(file_path: str) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """Try to load CSV with different encodings and separators."""
        # Simple heuristic for separator
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            first_line = f.readline()
            sep = ',' if ',' in first_line else '\t' if '\t' in first_line else ';'
        
        try:
            df = pd.read_csv(file_path, sep=sep)
            return df, {"rows": len(df), "columns": list(df.columns), "format": "csv"}
        except UnicodeDecodeError:
            # Fallback to latin1
            df = pd.read_csv(file_path, sep=sep, encoding='latin1')
            return df, {"rows": len(df), "columns": list(df.columns), "format": "csv", "encoding": "latin1"}

    @staticmethod
    def _load_excel(file_path: str) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        # Load all sheets to check, but return the first one by default for now
        # TODO: support multi-sheet selection in UI
        xls = pd.ExcelFile(file_path)
        sheet_names = xls.sheet_names
        df = pd.read_excel(file_path, sheet_name=0)
        return df, {"rows": len(df), "columns": list(df.columns), "sheets": sheet_names, "format": "excel"}

    @staticmethod
    def _load_spss(file_path: str) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        if pyreadstat is None:
            raise ImportError("pyreadstat is required for SPSS files. Install it via pip.")
        df, meta = pyreadstat.read_sav(file_path)
        return df, {
            "rows": len(df),
            "columns": list(df.columns),
            "variable_labels": meta.column_labels,
            "value_labels": meta.variable_value_labels,
            "format": "spss"
        }

    @staticmethod
    def _load_stata(file_path: str) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        if pyreadstat is None:
            raise ImportError("pyreadstat is required for Stata files. Install it via pip.")
        df, meta = pyreadstat.read_dta(file_path)
        return df, {
            "rows": len(df),
            "columns": list(df.columns),
            "variable_labels": meta.column_labels,
            "value_labels": meta.variable_value_labels,
            "format": "stata"
        }

    @staticmethod
    def _load_json(file_path: str) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        df = pd.read_json(file_path)
        return df, {"rows": len(df), "columns": list(df.columns), "format": "json"}
    
    @staticmethod
    def _load_parquet(file_path: str) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        df = pd.read_parquet(file_path)
        return df, {"rows": len(df), "columns": list(df.columns), "format": "parquet"}

    @staticmethod
    def get_file_info(df: pd.DataFrame) -> str:
        """Generate a brief summary string of the dataframe."""
        buffer = []
        buffer.append(f"📊 **QuantiProBot Data Summary**")
        buffer.append(f"Rows: {df.shape[0]}, Columns: {df.shape[1]}")
        buffer.append(f"Memory Usage: {df.memory_usage(deep=True).sum() / 1024:.2f} KB")
        buffer.append("\n**Variables:**")
        
        # List first 10 vars
        cols = list(df.columns)[:10]
        for col in cols:
            dtype = df[col].dtype
            missing = df[col].isnull().sum()
            buffer.append(f"- `{col}` ({dtype}): {missing} missing")
        
        if len(df.columns) > 10:
            buffer.append(f"...and {len(df.columns) - 10} more.")
            
        return "\n".join(buffer)

    @staticmethod
    def clean_data(df: pd.DataFrame) -> pd.DataFrame:
        """
        Automated cleaning:
        - Renames duplicate columns (suffixes like .1) to be readable
        - Drops empty rows
        - Fills NaN in numeric with Median
        - Fills NaN in categoricals with Mode
        """
        # Rename duplicated columns from pandas (.1, .2) to user-friendly names
        new_cols = []
        counts = {}
        import re
        for col in df.columns:
            # Check if it ends with .1, .2 etc. (pandas default for duplicates)
            orig_name = str(col)
            match = re.search(r'\.(\d+)$', orig_name)
            if match:
                potential_orig = orig_name[:match.start()]
                orig_name = potential_orig
                
            counts[orig_name] = counts.get(orig_name, 0) + 1
            if counts[orig_name] > 1:
                new_cols.append(f"{orig_name} (Duplicate {counts[orig_name]-1})")
            else:
                new_cols.append(orig_name)
        
        df.columns = new_cols
        
        df = df.dropna(how='all')
        
        # Numeric
        num_cols = df.select_dtypes(include=['number']).columns
        for col in num_cols:
            df[col] = df[col].fillna(df[col].median())
            
        # Categorical
        cat_cols = df.select_dtypes(exclude=['number']).columns
        for col in cat_cols:
            if not df[col].mode().empty:
                df[col] = df[col].fillna(df[col].mode()[0])
        
        return df

    @staticmethod
    def sort_data(df: pd.DataFrame, columns: List[str], ascending: bool = True) -> pd.DataFrame:
        """Sort dataset by given columns."""
        return df.sort_values(by=columns, ascending=ascending)

    @staticmethod
    def get_comprehensive_summary(df: pd.DataFrame) -> Dict[str, Any]:
        """Detailed info about all variables."""
        summary = {
            "total_rows": len(df),
            "total_cols": df.shape[1],
            "variables": []
        }
        for col in df.columns:
            summary['variables'].append({
                "name": col,
                "type": str(df[col].dtype),
                "missing": int(df[col].isnull().sum()),
                "unique": int(df[col].nunique())
            })
        return summary

