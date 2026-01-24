"""
LLM Integration Module
Provides intelligent analysis using LLM APIs (NVIDIA/DeepSeek, Groq, or Ollama)
"""

import os
import re
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path

# Try to load .env file
def load_env_file():
    """Load environment variables from .env file"""
    env_paths = [
        Path(__file__).parent.parent / '.env',
        Path.cwd() / '.env'
    ]
    
    for env_path in env_paths:
        if env_path.exists():
            try:
                with open(env_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#') and '=' in line:
                            key, value = line.split('=', 1)
                            key = key.strip()
                            value = value.strip().strip('"').strip("'")
                            if key and value and key not in os.environ:
                                os.environ[key] = value
                return True
            except Exception:
                pass
    return False

# Load .env file on import
load_env_file()

# Try importing LLM libraries
try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

from config import LLM_CONFIG


@dataclass
class LLMResponse:
    """Response from LLM"""
    success: bool
    content: str
    error: Optional[str] = None


class LLMIntegration:
    """
    LLM integration for intelligent analysis using NVIDIA API (DeepSeek R1)
    
    Features:
    - Intelligent error explanations
    - Abstract quality analysis
    - Paragraph classification fallback
    - Writing suggestions
    """
    
    def __init__(self, api_key: str = None):
        """
        Initialize LLM integration with NVIDIA API
        
        Args:
            api_key: NVIDIA API key (optional, can use env var)
        """
        self.api_key = api_key or os.environ.get("NVIDIA_API_KEY", LLM_CONFIG.get("nvidia_api_key", ""))
        self.model = LLM_CONFIG.get("nvidia_model", "deepseek-ai/deepseek-r1")
        self.max_tokens = LLM_CONFIG.get("max_tokens", 1024)
        self.temperature = LLM_CONFIG.get("temperature", 0.3)
        
        self._client = None
        self._available = False
        self._init_client()
    
    def _init_client(self):
        """Initialize the NVIDIA API client"""
        if OPENAI_AVAILABLE and self.api_key:
            try:
                self._client = OpenAI(
                    base_url="https://integrate.api.nvidia.com/v1",
                    api_key=self.api_key
                )
                # Test the connection
                test_response = self._client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": "test"}],
                    max_tokens=10
                )
                if test_response and test_response.choices:
                    self._available = True
                    print(f"[OK] NVIDIA DeepSeek R1 initialized successfully")
                else:
                    print("[ERROR] NVIDIA API test failed: no response")
                    self._available = False
            except Exception as e:
                print(f"[ERROR] Failed to initialize NVIDIA client: {e}")
                self._available = False
        else:
            if not OPENAI_AVAILABLE:
                print("[WARNING] openai library not installed. Run: pip install openai")
            if not self.api_key:
                print("[WARNING] NVIDIA API key not provided. Set NVIDIA_API_KEY environment variable.")
    
    def is_available(self) -> bool:
        """Check if LLM is available"""
        return self._available
    
    def generate(self, prompt: str, system_prompt: str = None) -> str:
        """
        Generate a response from the LLM
        
        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            
        Returns:
            Generated text response
        """
        if not self._available:
            return ""
        
        try:
            messages = []
            
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            
            messages.append({"role": "user", "content": prompt})
            
            response = self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                top_p=0.7
            )
            
            content = response.choices[0].message.content
            # DeepSeek R1 may include <think>...</think> tags, remove them
            content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL)
            return content.strip()
        except Exception as e:
            print(f"LLM generation error: {e}")
            return ""
    
    def explain_error(self, issue: Dict[str, Any]) -> str:
        """
        Generate an intelligent explanation for a formatting error
        
        Args:
            issue: Dictionary with keys: description, current_value, expected_value, location
            
        Returns:
            Human-friendly explanation of the error
        """
        if not self._available:
            return self._fallback_explanation(issue)
        
        prompt = f"""You are an academic writing assistant helping a student fix manuscript formatting issues.

Explain this formatting error in a helpful, educational way:

Location: {issue.get('location', 'Unknown')}
Issue: {issue.get('description', 'Formatting error')}
Current: {issue.get('current_value', 'Unknown')}
Expected: {issue.get('expected_value', 'Unknown')}

Provide:
1. A clear explanation of why this matters
2. How it affects journal submission
3. A brief tip for avoiding this in the future

Keep the response concise (2-3 sentences)."""

        system_prompt = "You are an expert academic editor helping students format their manuscripts correctly."
        
        try:
            response = self.generate(prompt, system_prompt)
            return response if response else self._fallback_explanation(issue)
        except Exception:
            return self._fallback_explanation(issue)
    
    def _fallback_explanation(self, issue: Dict[str, Any]) -> str:
        """Fallback explanation when LLM is unavailable"""
        description = issue.get('description', 'Formatting issue')
        current = issue.get('current_value', 'current format')
        expected = issue.get('expected_value', 'expected format')
        
        return (
            f"Your manuscript has {description.lower()}. "
            f"The current value ({current}) should be changed to {expected} "
            f"to match the journal template requirements."
        )
    
    def validate_issue(self, issue: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Use LLM to validate if a detected issue really needs correction.
        This helps reduce false positives.
        
        Args:
            issue: Dictionary with issue details
            
        Returns:
            Tuple of (should_fix, reason)
        """
        if not self._available:
            return True, "LLM not available for validation"
        
        prompt = f"""Is this formatting issue significant enough to require correction in an academic manuscript?

Issue: {issue.get('description', 'Unknown')}
Current: {issue.get('current_value', 'Unknown')}
Expected: {issue.get('expected_value', 'Unknown')}
Location: {issue.get('location', 'Unknown')}

Consider:
1. Is this a critical formatting requirement for journal submission?
2. Are there acceptable font variations (e.g., Times New Roman vs Times)?
3. Would this cause rejection by the journal editor?

Respond with: YES (needs correction) or NO (acceptable variation)
Brief reason:"""

        system_prompt = "You are an academic journal formatting expert. Be strict about formatting requirements."
        
        try:
            response = self.generate(prompt, system_prompt)
            needs_fix = 'yes' in response.lower().split('\n')[0].lower()
            return needs_fix, response.strip()
        except Exception:
            return True, "Validation failed, assuming correction needed"
    
    def classify_paragraph(self, text: str, context: str = "") -> str:
        """
        Use LLM to classify a paragraph when rules are uncertain
        
        Args:
            text: Paragraph text
            context: Optional context about paragraph position
            
        Returns:
            Classification string
        """
        if not self._available:
            return "unknown"
        
        prompt = f"""Classify this paragraph from an academic paper.

Paragraph: "{text[:500]}"
{f"Context: {context}" if context else ""}

Classification options (respond with ONLY one of these):
- journal_header (journal name, volume, ISSN, DOI)
- paper_title (the main title of the paper)
- author_info (author names, affiliations, emails)
- abstract_label (just the word "Abstract")
- keywords_label (just the word "Keywords")
- section_heading (like "Introduction", "Methodology", etc.)
- body (regular paragraph text)
- abstract_content (the abstract text itself)
- keywords_content (the keywords list)
- caption (figure or table caption)
- reference (bibliography entry)

Respond with ONLY the classification type, nothing else."""

        try:
            response = self.generate(prompt)
            response = response.strip().lower().replace(" ", "_")
            
            valid_types = [
                "journal_header", "paper_title", "author_info",
                "abstract_label", "keywords_label", "section_heading",
                "body", "abstract_content", "keywords_content",
                "caption", "reference"
            ]
            
            for valid_type in valid_types:
                if valid_type in response:
                    return valid_type
            
            return "unknown"
        except Exception:
            return "unknown"
    


def create_llm_integration(api_key: str = None) -> LLMIntegration:
    """
    Factory function to create LLM integration
    
    Args:
        api_key: NVIDIA API key
        
    Returns:
        LLMIntegration instance
    """
    return LLMIntegration(api_key=api_key)
