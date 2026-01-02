from src.core.file_manager import FileManager
from src.core.analyzer import Analyzer
import pandas as pd
import os

def test_engine():
    print("Testing QuantiBot Core Engine...")
    
    # 1. Create dummy CSV
    data = {
        'age': [25, 30, 35, 40, 45, 50, 55, 60],
        'salary': [50000, 60000, 75000, 80000, 90000, 100000, 110000, 120000],
        'score': [1.2, 2.3, 3.4, 4.5, 5.1, 6.2, 7.3, 8.4]
    }
    df = pd.DataFrame(data)
    test_file = "data/test_data.csv"
    if not os.path.exists('data'):
        os.makedirs('data')
    df.to_csv(test_file, index=False)
    print(f"Created {test_file}")

    # 2. Test FileManager
    print("\n--- FileManager Test ---")
    loaded_df, meta = FileManager.load_file(test_file)
    print(f"Loaded DataFrame: {loaded_df.shape}")
    print(f"Metadata: {meta}")
    
    # 3. Test Analyzer
    print("\n--- Analyzer Test ---")
    desc = Analyzer.get_descriptive_stats(loaded_df)
    print("Descriptive Stats Head:")
    print(desc.head())
    
    corr = Analyzer.get_correlation(loaded_df)
    print("\nCorrelation Matrix:")
    print(corr)
    
    # 4. Test AI Interpreter
    print("\n--- AI Interpreter Test ---")
    from src.core.ai_interpreter import AIInterpreter
    ai = AIInterpreter()
    
    # Test Fallback
    t_res = {'t_val': 2.5, 'p_val': 0.03}
    explanation = ai.interpret_results('ttest', t_res)
    print(f"Explanation (T-Test): {explanation}")
    
    # 5. Test Visualizer
    print("\n--- Visualizer Test ---")
    from src.core.visualizer import Visualizer
    plot_path = Visualizer.create_histogram(loaded_df, 'salary')
    print(f"Created Plot: {plot_path}")
    
    # 6. Test Manuscript with Image
    print("\n--- Manuscript Test ---")
    from src.writing.generator import ManuscriptGenerator
    gen = ManuscriptGenerator()
    doc_path = "data/test_manuscript.docx"
    gen.generate(
        filename=doc_path,
        title="QuantiBot Test Report",
        authors=["Test User"],
        abstract="Testing image embedding.",
        content_sections={"Intro": "Below is the figure."},
        stats_results=["(Stats would go here)"],
        images=[plot_path]
    )
    print(f"Created Manuscript: {doc_path} (Size: {os.path.getsize(doc_path)} bytes)")

    print("\n[OK] Verification Complete!")

if __name__ == "__main__":
    test_engine()
