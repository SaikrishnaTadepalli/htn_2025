import os
from typing import Optional

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


class Config:
    
    def __init__(self):
        self.DEEPGRAM_API_KEY: Optional[str] = os.getenv("DEEPGRAM_API_KEY")

        
    def validate_required_config(self) -> None:
        """Validate that required configuration values are present."""
        required_configs = []
        
        if not self.DEEPGRAM_API_KEY:
            required_configs.append("DEEPGRAM_API_KEY")
        
        if required_configs:
            missing_configs = ", ".join(required_configs)
            raise ValueError(f"Missing required environment variables: {missing_configs}")


config = Config()

DEEPGRAM_API_KEY = config.DEEPGRAM_API_KEY
