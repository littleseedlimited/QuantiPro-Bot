import math
from typing import Dict, Union, Optional
import statsmodels.stats.power as smp
import statsmodels.stats.api as sms

class Sampler:
    """
    Core calculator for sample size determination using various statistical methods.
    """
    
    # Standard Z-scores for Confidence Levels
    Z_SCORES = {
        '90%': 1.645,
        '95%': 1.96,
        '99%': 2.576
    }

    @staticmethod
    def calculate_cochran(
        p: float = 0.5, 
        e: float = 0.05, 
        confidence_level: str = '95%', 
        N: Optional[int] = None
    ) -> Dict[str, Union[int, str, float]]:
        """
        Calculates sample size using Cochran's Formula.
        
        Args:
            p (float): Estimated proportion of the population (default 0.5 for max variability).
            e (float): Margin of error (e.g., 0.05 for 5%).
            confidence_level (str): '90%', '95%', or '99%'.
            N (int, optional): Population size. If provided, applies finite population correction.
            
        Returns:
            dict: Result with 'sample_size', 'formula', and 'description'.
        """
        z = Sampler.Z_SCORES.get(confidence_level, 1.96)
        
        # Cochran's Formula for Infinite Population: n0 = (Z^2 * p * q) / e^2
        numerator = (z ** 2) * p * (1 - p)
        denominator = e ** 2
        n0 = numerator / denominator
        
        formula_desc = f"Cochran's (Infinite): ({z}^2 * {p} * {1-p}) / {e}^2"
        
        if N is not None:
            # Finite Population Correction: n = n0 / (1 + (n0 - 1) / N)
            n = n0 / (1 + ((n0 - 1) / N))
            formula_desc = f"Cochran's (Finite Correction, N={N})"
        else:
            n = n0
            
        return {
            'sample_size': math.ceil(n),
            'method': "Cochran's Formula",
            'formula': formula_desc,
            'confidence_level': confidence_level,
            'margin_of_error': e
        }

    @staticmethod
    def calculate_yamane(N: int, e: float = 0.05) -> Dict[str, Union[int, str, float]]:
        """
        Calculates sample size using Taro Yamane's simplified formula.
        n = N / (1 + N * e^2)
        """
        try:
            denominator = 1 + (N * (e ** 2))
            n = N / denominator
            
            return {
                'sample_size': math.ceil(n),
                'method': "Taro Yamane",
                'formula': f"n = {N} / (1 + {N}*{e}^2)",
                'population': N,
                'margin_of_error': e
            }
        except  Exception as ex:
             return {'error': str(ex)}

    @staticmethod
    def calculate_power_ttest(
        effect_size: float = 0.5, 
        alpha: float = 0.05, 
        power: float = 0.8, 
        ratio: float = 1.0
    ) -> Dict[str, Union[int, str, float]]:
        """
        Calculates sample size for Independent T-Test using G*Power equivalent.
        """
        try:
            analysis = smp.TTestIndPower()
            n = analysis.solve_power(
                effect_size=effect_size, 
                alpha=alpha, 
                power=power, 
                ratio=ratio
            )
            
            return {
                'sample_size': math.ceil(n), # Per group
                'total_sample': math.ceil(n) * 2, # Assuming equal groups for simplicity in output
                'method': "Power Analysis (T-Test)",
                'formula': f"G*Power (Effect={effect_size}, α={alpha}, Power={power})",
                'effect_size': effect_size
            }
        except Exception as e:
             return {'error': f"Calculation failed: {str(e)}"}
