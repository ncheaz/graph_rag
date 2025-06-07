import os
from dotenv import load_dotenv
from typing import Dict, Any

# Load environment variables from .env file
load_dotenv()

class Config:
    """Central configuration management for the GraphRAG system."""
    
    # Crawler configuration
    START_URL: str = os.getenv("CRAWLER_START_URL", "http://localhost:6006")
    MAX_DEPTH: int = int(os.getenv("CRAWLER_MAX_DEPTH", "3"))
    OUTPUT_DIR: str = os.getenv("CRAWLER_OUTPUT_DIR", "process/crawler")
    
    # Playwright settings
    HEADLESS: bool = os.getenv("PLAYWRIGHT_HEADLESS", "true").lower() == "true"
    TIMEOUT: int = int(os.getenv("PLAYWRIGHT_TIMEOUT", "30000"))
    
    @classmethod
    def to_dict(cls) -> Dict[str, Any]:
        """Return configuration as a dictionary for logging/debugging."""
        return {
            "START_URL": cls.START_URL,
            "MAX_DEPTH": cls.MAX_DEPTH,
            "OUTPUT_DIR": cls.OUTPUT_DIR,
            "HEADLESS": cls.HEADLESS,
            "TIMEOUT": cls.TIMEOUT
        }

# Initialize on import
config = Config()