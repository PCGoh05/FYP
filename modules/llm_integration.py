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

# LLM is disabled by default - using built-in fallback logic
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
                # Verify the API key by making a simple test call
                self._client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": "test"}],
                    max_tokens=1
                )
                self._available = True
            except Exception:
                self._client = None
                self._available = False
        else:
            self._available = False
    
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
            return content.strip() if content else ""
        except Exception:
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
    
    def analyze_template_rules(self, paragraphs_info: List[Dict]) -> Dict[str, Any]:
        """
        Use AI to analyze template paragraphs and extract formatting rules.
        This is the PRIMARY method for understanding template requirements.
        
        Args:
            paragraphs_info: List of dicts with 'text', 'font', 'size', 'bold', 'italic' info
            
        Returns:
            Dictionary of extracted rules for each element type
        """
        if not self._available:
            return {}
        
        # Format paragraphs for AI analysis - include more context
        formatted = []
        for i, p in enumerate(paragraphs_info[:40]):  # Analyze first 40 paragraphs
            text = p.get('text', '')[:100]
            font = p.get('font', 'Unknown')
            size = p.get('size', '?')
            bold = p.get('bold', 'Unknown')
            italic = p.get('italic', False)
            formatted.append(f"{i+1}. [{font}, {size}pt, italic={italic}] \"{text}\"")
        
        prompt = f"""Analyze this academic template and extract formatting rules.

IMPORTANT: DISTINGUISH BETWEEN JOURNAL TITLE AND PAPER TITLE!

In academic templates, there are TWO different titles:
1. JOURNAL TITLE - The name of the journal (e.g., "Journal of Informatics and Web Engineering")
   - Usually has "(Journal Title)" label
   - Often uses Palatino Linotype font
   - IGNORE THIS - we don't format journal names
   
2. PAPER TITLE - The title of the research paper itself (e.g., "Preparation template for...")
   - Usually has "(Title)" label WITHOUT "Journal"
   - This is what we need to extract rules for!
   - Look for instructions like "(24-Font size, Times New Roman)" - NO BOLD mentioned = bold: false

EXAMPLES OF INSTRUCTION TEXT PATTERNS:

PATTERN 1: "(24-Font size, bold Palatino Linotype)" - used for JOURNAL title
- Font variant: "Palatino Linotype Bold"  
- Bold formatting: FALSE (bold is part of font name, not a format instruction)

PATTERN 2: "(24-Font size, Times New Roman)" - used for PAPER title  
- Font: Times New Roman
- Bold: FALSE ❌ (bold is NOT mentioned at all!)

PATTERN 3: "(10-Font size, bold, Times New Roman)" - note the comma before bold
- Bold: TRUE ✅ (", bold," with commas = format instruction)

KEY RULES:
- "bold [FontName]" = font variant name, NOT bold formatting
- "(X-Font size, FontName)" with NO "bold" mentioned = bold: false
- Only ", bold," or ", bold)" with commas means bold: true

PARAGRAPHS FROM TEMPLATE:
{chr(10).join(formatted)}

For the "title" field, extract rules for the PAPER TITLE (marked with "(Title)"), NOT the journal title!

Return ONLY valid JSON:
{{
    "title": {{"font": "FontName", "size": NUM, "bold": false, "italic": false}},
    "heading": {{"font": "FontName", "size": NUM, "bold": BOOL, "italic": BOOL}},
    "body": {{"font": "FontName", "size": NUM, "bold": false, "italic": false}},
    "abstract": {{"font": "FontName", "size": NUM, "bold": false, "italic": false}},
    "reference": {{"font": "FontName", "size": NUM, "bold": false, "italic": false}},
    "caption": {{"font": "FontName", "size": NUM, "bold": false, "italic": BOOL}}
}}

CRITICAL FOR JIWE TEMPLATE: 
- Paper Title instruction is "(24-Font size, Times New Roman)" 
- This means: font="Times New Roman", size=24, bold=FALSE (bold not mentioned!)"""

        system_prompt = """You are analyzing academic template formatting instructions.
CRITICAL: Look for "(Title)" to find PAPER title rules, ignore "(Journal Title)".
For "(24-Font size, Times New Roman)" - bold is FALSE because it's not mentioned.
Only return bold=true if there's ", bold," with commas."""
        
        try:
            response = self.generate(prompt, system_prompt)
            # Parse JSON from response
            import json
            import re
            
            response = response.strip()
            
            # DEBUG: Print AI response
            print(f"[DEBUG] AI Template Analysis Response:")
            print(f"{response[:500]}...")
            
            # Try to extract JSON from various formats
            # Method 1: Direct parse
            try:
                rules = json.loads(response)
                rules['_ai_extracted'] = True
                print(f"[DEBUG] AI Extracted Title Rule: {rules.get('title', {})}")
                return rules
            except json.JSONDecodeError:
                pass
            
            # Method 2: Remove markdown code blocks
            if response.startswith('```'):
                lines = response.split('\n')
                # Remove first and last lines if they are markdown markers
                if lines[0].startswith('```'):
                    lines = lines[1:]
                if lines and lines[-1].strip() == '```':
                    lines = lines[:-1]
                response = '\n'.join(lines)
                try:
                    rules = json.loads(response)
                    rules['_ai_extracted'] = True
                    print(f"[DEBUG] AI Extracted Title Rule: {rules.get('title', {})}")
                    return rules
                except json.JSONDecodeError:
                    pass
            
            # Method 3: Find JSON object in response using regex
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                try:
                    rules = json.loads(json_match.group())
                    rules['_ai_extracted'] = True
                    print(f"[DEBUG] AI Extracted Title Rule: {rules.get('title', {})}")
                    return rules
                except json.JSONDecodeError:
                    pass
            
            print(f"[DEBUG] AI failed to return valid JSON")
            return {}
        except Exception as e:
            print(f"[DEBUG] AI template analysis error: {e}")
            return {}
    
    def classify_paragraphs_batch(self, paragraphs: List[str]) -> List[str]:
        """
        Classify multiple paragraphs in a single API call for efficiency.
        
        Args:
            paragraphs: List of paragraph texts
            
        Returns:
            List of classification strings
        """
        if not self._available:
            return ["unknown"] * len(paragraphs)
        
        # Format paragraphs with indices
        formatted = []
        for i, text in enumerate(paragraphs[:30]):  # Limit to 30 paragraphs per call
            preview = text[:100].replace('\n', ' ')
            formatted.append(f"{i+1}. \"{preview}\"")
        
        prompt = f"""Classify each paragraph from this academic paper.

PARAGRAPHS:
{chr(10).join(formatted)}

CLASSIFICATION TYPES:
- journal_header (journal name, volume, dates, ISSN)
- paper_title (the main title)
- author_info (author names, affiliations)
- abstract_content (abstract text)
- keywords_content (keywords list)
- section_heading (like INTRODUCTION, METHODOLOGY)
- body (regular paragraphs)
- caption (figure/table captions)
- reference (bibliography entries)

Return ONLY a JSON array with classifications in order, like:
["paper_title", "author_info", "abstract_content", "section_heading", "body", ...]

IMPORTANT: Return ONLY the JSON array, nothing else. Must have exactly {len(paragraphs[:30])} items."""

        system_prompt = "You are an expert at classifying academic paper content. Be accurate and consistent."
        
        try:
            response = self.generate(prompt, system_prompt)
            import json
            response = response.strip()
            if response.startswith('```'):
                lines = response.split('\n')
                response = '\n'.join(lines[1:-1] if lines[-1] == '```' else lines[1:])
            
            classifications = json.loads(response)
            
            # Ensure we have enough classifications
            while len(classifications) < len(paragraphs):
                classifications.append("body")
            
            return classifications[:len(paragraphs)]
        except Exception:
            return ["unknown"] * len(paragraphs)
    
    def validate_correction(self, original_format: str, proposed_format: str, 
                          paragraph_text: str, paragraph_type: str) -> Tuple[bool, str]:
        """
        Validate if a proposed formatting correction is appropriate.
        
        Args:
            original_format: Description of original formatting
            proposed_format: Description of proposed formatting
            paragraph_text: The paragraph text
            paragraph_type: The classified type of paragraph
            
        Returns:
            Tuple of (should_apply, reason)
        """
        if not self._available:
            return True, "AI validation unavailable"
        
        prompt = f"""Should this formatting correction be applied?

PARAGRAPH TYPE: {paragraph_type}
TEXT: "{paragraph_text[:100]}..."
CURRENT FORMAT: {original_format}
PROPOSED FORMAT: {proposed_format}

Consider:
1. Is the paragraph classified correctly?
2. Is the proposed format appropriate for this content?
3. Would this correction improve the manuscript?

Respond with EXACTLY this format:
DECISION: YES or NO
REASON: (brief explanation)"""

        system_prompt = "You are an academic formatting expert. Be strict but fair."
        
        try:
            response = self.generate(prompt, system_prompt)
            decision = "yes" in response.lower().split('\n')[0].lower()
            return decision, response.strip()
        except Exception:
            return True, "Validation failed, applying correction"


def create_llm_integration(api_key: str = None) -> LLMIntegration:
    """
    Factory function to create LLM integration
    
    Args:
        api_key: NVIDIA API key
        
    Returns:
        LLMIntegration instance
    """
    return LLMIntegration(api_key=api_key)
