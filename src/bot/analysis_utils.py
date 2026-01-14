from typing import Dict, Any

ANALYSIS_GUIDE = {
    'ttest': {
        'name': 'Independent T-Test',
        'description': 'Compares the means of two independent groups to determine if they are significantly different.',
        'variables': '1 Categorical (2 groups) + 1 Numeric.',
        'use_case': 'Comparing test scores between boys and girls, or salary between two departments.'
    },
    'anova': {
        'name': 'One-Way ANOVA',
        'description': 'Compares the means of three or more independent groups.',
        'variables': '1 Categorical (3+ groups) + 1 Numeric.',
        'use_case': 'Comparing crop yields between four different types of fertilizer.'
    },
    'mwu': {
        'name': 'Mann-Whitney U',
        'description': 'A non-parametric test to compare differences between two groups when data is not normally distributed.',
        'variables': '1 Categorical (2 groups) + 1 Ordinal/Numeric.',
        'use_case': 'Comparing rankings or non-normal satisfaction scores between two groups.'
    },
    'correlation': {
        'name': 'Pearson Correlation',
        'description': 'Measures the linear strength and direction of the relationship between two variables.',
        'variables': '2 Numeric variables.',
        'use_case': 'Checking the relationship between advertising spend and sales revenue.'
    },
    'regression': {
        'name': 'Regression Analysis',
        'description': 'Predicts a dependent variable based on one or more independent predictor variables.',
        'types': {
            'linear': {
                'name': 'Linear Regression',
                'desc': 'Predicts a continuous numeric outcome.',
                'vars': '1 Numeric DV + 1+ Numeric IVs'
            },
            'logistic': {
                'name': 'Logistic Regression',
                'desc': 'Predicts binary (Yes/No) outcomes using Odds Ratios.',
                'vars': '1 Binary DV + 1+ Numeric/Categorical IVs'
            },
            'multiple': {
                'name': 'Multiple Regression',
                'desc': 'Linear regression with multiple predictors.',
                'vars': '1 Numeric DV + 2+ Numeric IVs'
            }
        },
        'use_case': 'Predicting house prices (Linear) or success probability (Logistic).'
    },
    'crosstab': {
        'name': 'Crosstab (Chi-Square)',
        'description': 'Examines the association between two categorical variables.',
        'variables': '2 Categorical variables.',
        'use_case': 'Checking if choice of transport (Bus, Car, Train) depends on gender.'
    },
    'descriptive': {
        'name': 'Descriptive Statistics',
        'description': 'Summarizes the main features of a dataset (Mean, Median, Std Dev, etc.).',
        'variables': 'Numeric variables.',
        'use_case': 'Getting an overview of the average age, income, and distribution of your sample.'
    },
    'frequencies': {
        'name': 'Frequencies & Tabulation',
        'description': 'Counts how often each value occurs in a variable.',
        'variables': 'Categorical or Discrete variables.',
        'use_case': 'Finding the number of respondents per city or the percentage of "Yes/No" answers.'
    },
    'reliability': {
        'name': 'Reliability Analysis',
        'description': "Measures the internal consistency of a scale (Cronbach's Alpha).",
        'variables': 'Multiple Numeric/Ordinal items from the same scale.',
        'use_case': 'Testing if several questionnaire items effectively measure the same underlying construct (e.g., Job Satisfaction).'
    }
}
