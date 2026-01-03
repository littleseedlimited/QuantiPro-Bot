import pandas as pd
from typing import Dict, Any

class DataMapper:
    """Helper for mapping variable values to labels."""

    @staticmethod
    def parse_mapping_string(mapping_str: str) -> Dict[Any, str]:
        """
        Parses a string like "1=Male, 2=Female" into a dictionary.
        Handles numeric keys and string values.
        """
        mapping = {}
        # Split by comma or newline
        pairs = [p.strip() for p in mapping_str.replace('\n', ',').split(',') if p.strip()]
        
        for pair in pairs:
            if '=' not in pair:
                continue
            
            key_str, val_str = pair.split('=', 1)
            key_str = key_str.strip()
            val_str = val_str.strip()
            
            # Try to convert key to number (int/float)
            try:
                if '.' in key_str:
                    key = float(key_str)
                else:
                    key = int(key_str)
            except ValueError:
                key = key_str # Keep as string if not number
                
            mapping[key] = val_str
            
        return mapping

    @staticmethod
    def apply_mapping(df: pd.DataFrame, column: str, mapping: Dict[Any, str]) -> pd.DataFrame:
        """Applies the mapping to the dataframe column."""
        if column not in df.columns:
            return df
            
        df = df.copy()
        # Ensure column type matches mapping keys (roughly)
        try:
            df[column] = df[column].map(mapping).fillna(df[column])
        except Exception:
            pass # Fallback if map fails types
            
        return df
