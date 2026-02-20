"""
Configuration file for Gemini model selection.
Allows easy switching between models and fallback logic.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# Model configuration
PRIMARY_MODEL = "gemini-2.0-flash"

# Fallback model (lighter, used on rate-limit retry)
FALLBACK_MODEL = "gemini-2.0-flash-lite"

# Get API keys
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
SCRAPFLY_KEY = os.getenv("SCRAPFLY_KEY")

def get_model_name(use_fallback: bool = False) -> str:
    """
    Get the model name to use.
    
    Args:
        use_fallback: If True, use fallback model instead of primary
    
    Returns:
        Model name string
    """
    if use_fallback:
        return FALLBACK_MODEL
    return PRIMARY_MODEL
