
import pandas as pd
import sys
import os

# Add src to path
sys.path.append(os.getcwd())

from src.core.analyzer import Analyzer

def test_crosstab():
    df = pd.DataFrame({
        'Gender': ['Male', 'Female', 'Male', 'Female', 'Male'],
        'Satisfaction': ['High', 'Low', 'Medium', 'High', 'Low']
    })
    
    print("Testing Crosstab...")
    try:
        res = Analyzer.crosstab(df, 'Gender', 'Satisfaction', show_row_pct=True, show_col_pct=True, show_total_pct=True)
        print("Crosstab Result Keys:", res.keys())
        
        counts = res['counts']
        print("\nCounts Shape:", counts.shape)
        print("Counts Index:", counts.index.tolist())
        print(" 'Total' in Index?", 'Total' in counts.index)
        
        if 'row_percentages' in res:
            print("\nRow Pct Index:", res['row_percentages'].index.tolist())
            
        # Simmons formatting
        print("\nSimulating Mobile Format:")
        formatted = Analyzer.format_crosstab_mobile(res)
        print(formatted[:100] + "...")
        print("Success!")
        
    except Exception as e:
        print(f"FAILED: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_crosstab()
