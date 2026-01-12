import os
import re
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class AIInterpreter:
    """
    AI-Powered Statistical Interpreter.
    Attributes:
        api_key (str): OpenAI API Key.
    """
    
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            logger.warning("OPENAI_API_KEY not found. AI interpretation will use templates.")

    @staticmethod
    def _clean_formatting(text: str) -> str:
        """Remove asterisks and clean up formatting for Telegram."""
        # Remove markdown bold/italic asterisks
        text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)  # **bold** -> bold
        text = re.sub(r'\*([^*]+)\*', r'\1', text)      # *italic* -> italic
        text = re.sub(r'__([^_]+)__', r'\1', text)      # __bold__ -> bold
        text = re.sub(r'_([^_]+)_', r'\1', text)        # _italic_ -> italic
        # Clean up extra whitespace
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()

    async def interpret_results(self, analysis_type: str, results: Dict[str, Any]) -> str:
        """
        Generate a plain-language explanation of the results.
        """
        if self.api_key:
            try:
                from openai import AsyncOpenAI
                client = AsyncOpenAI(api_key=self.api_key)
                
                prompt = (
                    f"You are a PhD statistician for 'QuantiProBot'. Explain the following {analysis_type} results "
                    f"in plain, professional language suitable for a research manuscript results section.\n\n"
                    f"Results JSON: {str(results)}\n\n"
                    "IMPORTANT: Do NOT use markdown formatting like asterisks or underscores. "
                    "Write in plain text only. Focus on whether the result is significant, "
                    "the effect size, and a brief implication. Keep it under 150 words."
                )
                
                response = await client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": "You are a professional statistical consultant. Never use asterisks or markdown formatting in your responses."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=300,
                    temperature=0.7,
                    timeout=30.0  # 30 second timeout
                )
                content = self._clean_formatting(response.choices[0].message.content)
                return f"📊 Interpretation:\n\n{content}"
            except TimeoutError:
                logger.warning("OpenAI API timeout - using fallback")
                return self._template_fallback(analysis_type, results)
            except Exception as e:
                logger.error(f"OpenAI error: {e}")
                return self._template_fallback(analysis_type, results)
        else:
            return self._template_fallback(analysis_type, results)



    async def chat(self, user_msg: str, file_path: str = None, analysis_history: list = None, visuals_history: list = None) -> str:
        """
        Context-aware chat about the user's data and analysis.
        """
        if not self.api_key:
            return "⚠️ AI features are not enabled (API Key missing). I can only run statistical tests."

        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=self.api_key)
            
            # 1. Build Context String
            context_text = ""
            
            # Recent Analysis (last 3)
            if analysis_history:
                context_text += "\n\nRECENT ANALYSIS RESULTS:\n"
                for i, item in enumerate(analysis_history[-3:], 1):
                    context_text += f"{i}. {item.get('test')} on {item.get('vars')}: {str(item.get('data'))[:500]}\n"
            
            # Recent Visuals (last 3)
            if visuals_history:
                context_text += "\n\nRECENT CHARTS GENERATED:\n"
                for i, item in enumerate(visuals_history[-3:], 1):
                    # SAFETY CHECK: If someone appended a string path instead of a dict
                    if isinstance(item, str):
                        context_text += f"{i}. Chart: {os.path.basename(item)}\n"
                        continue
                        
                    # item keys: path, title, type, data
                    chart_info = f"{i}. {item.get('title', 'Chart')} ({item.get('type', 'unknown')})\n"
                    if item.get('data'):
                         # Include descriptive stats captured for the chart
                         chart_info += f"   Underlying Data/Stats: {str(item.get('data'))[:600]}\n"
                    context_text += chart_info

            system_prompt = (
                "You are an expert statistical consultant assisting a researcher. "
                "You have access to the context of their recent analysis below.\n"
                "When asked to 'explain this' or interpret a result, refer specifically to the data provided in the context.\n"
                "IMPORTANT: If the user asks to 'discuss the results' or similar, look for the MOST RECENT entry in the 'RECENT ANALYSIS RESULTS' section and provide a detailed scientific interpretation of those specific findings.\n"
                "If the user asks about a histogram, look for the 'Underlying Data/Stats' to describe the distribution (mean, standard deviation, skewness based on mean/median comparison).\n"
                "If the user asks about a radar chart, look for the 'means' in the stats to see which variables have high or low values relative to others.\n"
                "If the user asks about a scatter plot, use the 'correlation' value to describe the strength and direction of the relationship.\n"
                "Use professional but accessible language. "
                "Do NOT use markdown bold/italic (**text**) in your final output, use plain text only."
                f"{context_text}"
            )

            response = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_msg}
                ],
                max_tokens=400,
                temperature=0.7
            )
            
            return self._clean_formatting(response.choices[0].message.content)

        except Exception as e:
            logger.error(f"Chat error: {e}")
            return "I encountered an error trying to process your request."

    async def generate_research_suggestions(self, topic: str) -> Dict[str, Any]:
        """
        Generate research questions and hypotheses based on a topic/title.
        """
        if not self.api_key:
            return {
                "questions": "1. What is the impact of this topic?\n2. How do variables relate?",
                "hypotheses": "H1: There is a significant effect.\nH2: There is a significant relationship."
            }

        try:
            from openai import AsyncOpenAI
            import json
            client = AsyncOpenAI(api_key=self.api_key)
            
            prompt = f"""
            You are a senior research consultant. Based on the following research topic/title, suggest 3 research questions and 3 corresponding hypotheses.
            Topic: {topic}
            
            Return ONLY a JSON object with these keys: "questions", "hypotheses".
            Format the values as plain text strings with numbered lists starting with 1., 2., 3....
            Example: {{"questions": "1. Q1\n2. Q2", "hypotheses": "H1. H1\nH2. H2"}}
            """

            response = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=600,
                temperature=0.7
            )
            
            content = response.choices[0].message.content.strip()
            if content.startswith("```json"):
                content = content[7:-3]
            elif content.startswith("```"):
                content = content[3:-3]
                
            return json.loads(content)
        except Exception as e:
            logger.error(f"Error generating suggestions: {e}")
            return {
                "questions": "1. What is the impact of this topic?\n2. How do variables relate?",
                "hypotheses": "H1: There is a significant effect.\nH2: There is a significant relationship."
            }


    def _template_fallback(self, analysis_type: str, results: Dict[str, Any]) -> str:
        """Simple templates for when no AI is available."""
        if analysis_type == "descriptive":
            return (
                "📊 Interpretation:\n\n"
                "The descriptive statistics show the central tendency (mean, median) "
                "and dispersion (std, min, max) of your numeric variables. Look for outliers or unexpected values."
            )
        elif analysis_type == "ttest":
            p = results.get('p_val', 1.0)
            sig = "significant" if p < 0.05 else "not significant"
            return (
                f"📊 Interpretation:\n\n"
                f"The T-test result was statistically {sig} (p={p:.4f}). "
                f"This suggests that the difference between the groups is {sig}."
            )
        elif analysis_type == "correlation":
            return (
                "📊 Interpretation:\n\n"
                "The correlation matrix shows relationships between variables. "
                "Values close to +1 or -1 indicate strong relationships, while values near 0 suggest weak or no linear relationship."
            )
        elif analysis_type == "regression":
            r2 = results.get('r_squared', 0)
            return f"📊 Interpretation:\n\nThe regression model explains {r2:.2%} of the variance in the outcome variable."
        elif analysis_type == "chi2":
            p = results.get('p_val', 1.0)
            sig = "significant" if p < 0.05 else "not significant"
            return f"📊 Interpretation:\n\nThe Chi-square test was statistically {sig} (p={p:.4f})."
        elif analysis_type == "mwu":
            p = results.get('p-val', results.get('p_val', 1.0))
            sig = "significant" if p < 0.05 else "not significant"
            return f"📊 Interpretation:\n\nThe Mann-Whitney U test results indicate a {sig} difference between the groups (p={p:.4f})."
        elif analysis_type == "anova":
            p = results.get('p_val', 1.0)
            sig = "significant" if p < 0.05 else "not significant"
            return f"📊 Interpretation:\n\nThe ANOVA results show a {sig} difference between the group means (p={p:.4f})."
        elif analysis_type == "reliability":
            alpha = results.get('alpha', 0)
            return f"📊 Interpretation:\n\nCronbach's Alpha = {alpha:.3f}. Values above 0.7 are generally acceptable for reliability."
        
        return "📊 Analysis complete. Review the results above."

    async def generate_discussion(self, 
                                   title: str,
                                   objectives: str,
                                   questions: str,
                                   hypotheses: str,
                                   analysis_history: list,
                                   descriptive_stats: str = "",
                                   **kwargs) -> str:

        """
        Generate a comprehensive Discussion section summarizing all findings.
        
        Args:
            title: Research title
            objectives: Research objectives
            questions: Research questions
            hypotheses: Research hypotheses  
            analysis_history: List of analysis records with test, vars, result, data
            descriptive_stats: String of descriptive statistics
            
        Returns:
            Comprehensive discussion text
        """
        # Build analysis summary
        analyses_text = []
        for i, analysis in enumerate(analysis_history, 1):
            test_type = analysis.get('test', 'Unknown')
            vars_used = analysis.get('vars', 'N/A')
            data = analysis.get('data', {})
            
            # Extract key statistics
            if test_type == 'T-Test':
                stat_summary = f"t={data.get('t_val', 'N/A')}, p={data.get('p_val', 'N/A')}"
            elif test_type == 'Correlation':
                stat_summary = f"r={data.get('r', 'N/A')}"
            elif test_type == 'Regression':
                stat_summary = f"R²={data.get('r_squared', 'N/A')}, p={data.get('f_pvalue', 'N/A')}"
            elif test_type == 'Chi-Square':
                stat_summary = f"χ²={data.get('chi2', 'N/A')}, p={data.get('p_val', 'N/A')}"
            elif test_type == 'Reliability':
                stat_summary = f"α={data.get('alpha', 'N/A')}"
            else:
                stat_summary = str(data)[:100]
            
            analyses_text.append(f"{i}. {test_type} ({vars_used}): {stat_summary}")
        
        analyses_summary = "\n".join(analyses_text) if analyses_text else "No analyses performed."
        
        if self.api_key:
            try:
                from openai import AsyncOpenAI
                client = AsyncOpenAI(api_key=self.api_key)
                
                # Word count instruction based on target
                min_words = kwargs.get('min_word_count', 1500)
                max_words = kwargs.get('max_word_count', 2500)
                
                # Calculate approximate tokens needed (1 word ≈ 1.3 tokens)
                max_tokens = int(max_words * 1.5)
                if max_tokens < 2000:
                    max_tokens = 2000
                if max_tokens > 4000:
                    max_tokens = 4000
                
                prompt = f"""You are Dr. Sarah Chen, a senior academic writing consultant with 20+ years experience in research methodology.
Write a COMPREHENSIVE manuscript content for a research paper based on the following:

RESEARCH CONTEXT:
- Title: {title}
- Objectives: {objectives}
- Research Questions: {questions}
- Hypotheses: {hypotheses}

ANALYSIS RESULTS:
{analyses_summary}

DESCRIPTIVE STATISTICS (Summary):
{descriptive_stats[:500] if descriptive_stats else 'Not provided'}

Write comprehensive manuscript content that includes:
1. INTRODUCTION - Background and rationale (2-3 paragraphs)
2. KEY FINDINGS - Summary of results (2-3 paragraphs)
3. INTERPRETATION - Explain each analysis result in context of research questions
4. HYPOTHESIS TESTING - State whether hypotheses were SUPPORTED or NOT SUPPORTED with evidence
5. IMPLICATIONS - Practical and theoretical implications (1-2 paragraphs)
6. LIMITATIONS - Acknowledge study limitations (1 paragraph)
7. FUTURE RESEARCH - Suggest directions for future research (1 paragraph)
8. CONCLUSION - Summary of key takeaways (1 paragraph)

CRITICAL WORD COUNT REQUIREMENT:
Your response MUST be between {min_words} and {max_words} words.
This is a strict requirement. Write detailed, comprehensive content to meet this word count.
Expand on each point thoroughly. Add context, examples, and detailed explanations.

IMPORTANT FORMATTING:
- Use clear paragraph structure
- Do NOT use markdown, asterisks, or bullet points
- Write in formal academic prose
- Start directly with the content (no headers or section labels)"""
                
                response = await client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": "You are a senior academic writing consultant. Write detailed, comprehensive academic content. Your output MUST meet the specified word count requirement. Write in formal, clear academic prose without any markdown formatting."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=max_tokens,
                    temperature=0.7,
                    timeout=90.0  # 90s timeout for long reports
                )
                content = self._clean_formatting(response.choices[0].message.content)
                return content
            except Exception as e:
                logger.error(f"OpenAI error in generate_discussion: {e}")
                return self._discussion_fallback(title, analysis_history)
        else:
            return self._discussion_fallback(title, analysis_history)
    
    
    async def generate_references(self, title: str, objectives: str, count: int = 5) -> list:
        """
        Generate relevant academic references based on the research topic using AI.
        Returns a list of dicts: {'authors': ..., 'year': ..., 'title': ..., 'source': ...}
        """
        if not self.api_key:
            return []

        try:
            from openai import AsyncOpenAI
            import json
            client = AsyncOpenAI(api_key=self.api_key)
            
            prompt = f"""
            You are an academic research assistant.
            Generate {count} REAL or highly plausible academic references relevant to this study:
            Title: {title}
            Objectives: {objectives}
            
            Return ONLY a JSON array of objects with these keys: "authors", "year", "title", "source".
            Ensure they are formatted for APA 7th edition citation.
            Example: [{{"authors": "Smith, J.", "year": "2023", "title": "Study Name", "source": "Journal of X"}}]
            """

            response = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=600,
                temperature=0.7
            )
            
            content = response.choices[0].message.content.strip()
            # Clean markdown code blocks if present
            if content.startswith("```json"):
                content = content[7:-3]
            elif content.startswith("```"):
                content = content[3:-3]
                
            refs = json.loads(content)
            return refs
        except Exception as e:
            logger.error(f"Error generating references: {e}")
            return []

    def _discussion_fallback(self, title: str, analysis_history: list) -> str:
        """Generate a basic discussion when AI is not available."""
        findings = []
        for analysis in analysis_history:
            test_type = analysis.get('test', 'Unknown')
            data = analysis.get('data', {})
            
            if test_type == 'T-Test':
                p = data.get('p_val', 1.0)
                sig = "significant" if p < 0.05 else "not significant"
                findings.append(f"The T-test results were statistically {sig} (p={p:.4f}).")
            elif test_type == 'Regression':
                r2 = data.get('r_squared', 0)
                findings.append(f"The regression model explained {r2:.1%} of variance in the outcome.")
            elif test_type == 'Correlation':
                r = data.get('r', 0)
                findings.append(f"A correlation of r={r:.3f} was observed between the variables.")
            elif test_type == 'Chi-Square':
                p = data.get('p_val', 1.0)
                sig = "significant" if p < 0.05 else "not significant"
                findings.append(f"The Chi-square test was statistically {sig} (p={p:.4f}).")
        
        findings_text = " ".join(findings) if findings else "No specific findings to report."
        
        return f"""The present study, titled "{title}", investigated the research objectives through a series of statistical analyses.

Key Findings: {findings_text}

These findings have important implications for the field and provide direction for future research. However, like all studies, this research has limitations that should be considered when interpreting the results.

Further investigation with larger sample sizes and additional variables would strengthen these conclusions. Researchers are encouraged to replicate these findings in different contexts and populations.

The results contribute to the existing body of literature and offer practical recommendations for practitioners in the field."""
