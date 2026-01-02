import pandas as pd
import os
import sys
import unittest
from unittest.mock import MagicMock, AsyncMock

# Add current directory to path
sys.path.append(os.getcwd())

from src.core.file_manager import FileManager
from src.bot.interview import InterviewManager
from src.bot.handlers import get_column_markup

class TestFixes(unittest.TestCase):
    def test_duplicate_renaming(self):
        print("\nTesting Duplicate Column Renaming...")
        # Simulating pandas' behavior when loading CSV with duplicate headers
        # Pandas adds .1, .2 etc.
        df = pd.DataFrame({
            'Age': [20, 30],
            'Age.1': [21, 31],
            'Sex': ['M', 'F'],
            'Sex.1': ['M', 'F'],
            'Sex.2': ['M', 'F']
        })
        
        cleaned_df = FileManager.clean_data(df)
        cols = list(cleaned_df.columns)
        print(f"Original: {list(df.columns)}")
        print(f"Cleaned:  {cols}")
        
        self.assertIn('Age', cols)
        self.assertIn('Age (Duplicate 1)', cols)
        self.assertIn('Sex', cols)
        self.assertIn('Sex (Duplicate 1)', cols)
        self.assertIn('Sex (Duplicate 2)', cols)

    def test_column_markup_humanization(self):
        print("\nTesting Column Markup Humanization...")
        cols = ['Age', 'Age.1', 'Job Title.1', 'Salary']
        markup = get_column_markup(cols)
        
        # markup is a ReplyKeyboardMarkup
        # We need to check the buttons
        keyboard = markup.keyboard
        flattened_buttons = [btn for row in keyboard for btn in row]
        # Avoid printing emoji to terminal to prevent UnicodeEncodeError
        print(f"Labels (first 5): {[str(b).encode('ascii', 'ignore').decode() for b in flattened_buttons[:5]]}")
        
        # Check for existence (handling the checkmark if it's there, but here it shouldn't be)
        self.assertTrue(any('Age' in str(b) for b in flattened_buttons))
        self.assertTrue(any('Age (Dup 1)' in str(b) for b in flattened_buttons))
        self.assertTrue(any('Job Title (Dup 1)' in str(b) for b in flattened_buttons))

    def test_state_clearing(self):
        print("\nTesting State Clearing...")
        context = MagicMock()
        context.user_data = {
            'awaiting_corr_vars': True,
            'awaiting_regression_dep': True,
            'selected_corr_vars': ['some', 'var'],
            'analysis_history': []
        }
        update = MagicMock()
        update.message.reply_text = AsyncMock()
        
        import asyncio
        asyncio.run(InterviewManager.start_interview(update, context))
        
        print(f"Flags after start_interview: { {k: v for k, v in context.user_data.items() if k.startswith('awaiting_')} }")
        
        self.assertFalse(context.user_data['awaiting_corr_vars'])
        self.assertFalse(context.user_data['awaiting_regression_dep'])
        self.assertEqual(len(context.user_data['selected_corr_vars']), 0)

if __name__ == '__main__':
    unittest.main()
