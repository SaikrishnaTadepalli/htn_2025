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
        self.GROQ_API_KEY: Optional[str] = os.getenv("GROQ_API_KEY")
        self.ELEVEN_LABS_API_KEY: Optional[str] = os.getenv("ELEVEN_LABS_API_KEY")
        self.GOOGLE_APPLICATION_CREDENTIALS: Optional[str] = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

        
    def validate_required_config(self) -> None:
        """Validate that required configuration values are present."""
        required_configs = []
        
        if not self.DEEPGRAM_API_KEY:
            required_configs.append("DEEPGRAM_API_KEY")
        
        if not self.GROQ_API_KEY:
            required_configs.append("GROQ_API_KEY")
        
        if not self.ELEVEN_LABS_API_KEY:
            required_configs.append("ELEVEN_LABS_API_KEY")
        
        if not self.GOOGLE_APPLICATION_CREDENTIALS:
            required_configs.append("GOOGLE_APPLICATION_CREDENTIALS")
        
        if required_configs:
            missing_configs = ", ".join(required_configs)
            raise ValueError(f"Missing required environment variables: {missing_configs}")


config = Config()

DEEPGRAM_API_KEY = config.DEEPGRAM_API_KEY
GROQ_API_KEY = config.GROQ_API_KEY
ELEVEN_LABS_API_KEY = config.ELEVEN_LABS_API_KEY
GOOGLE_APPLICATION_CREDENTIALS = config.GOOGLE_APPLICATION_CREDENTIALS
