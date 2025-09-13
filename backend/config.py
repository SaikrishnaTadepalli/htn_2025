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

        # Spotify API credentials (optional)
        self.SPOTIFY_CLIENT_ID: Optional[str] = os.getenv("SPOTIFY_CLIENT_ID")
        self.SPOTIFY_CLIENT_SECRET: Optional[str] = os.getenv("SPOTIFY_CLIENT_SECRET")
        self.SPOTIFY_REDIRECT_URI: Optional[str] = os.getenv("SPOTIFY_REDIRECT_URI", "http://localhost:8080/callback")

        
    def validate_required_config(self) -> None:
        """Validate that required configuration values are present."""
        required_configs = []
        
        if not self.DEEPGRAM_API_KEY:
            required_configs.append("DEEPGRAM_API_KEY")
        
        if not self.GROQ_API_KEY:
            required_configs.append("GROQ_API_KEY")
        
        if not self.ELEVEN_LABS_API_KEY:
            required_configs.append("ELEVEN_LABS_API_KEY")
        if not self.SPOTIFY_CLIENT_ID:
            required_configs.append("SPOTIFY_CLIENT_ID")
        if not self.SPOTIFY_CLIENT_SECRET:
            required_configs.append("SPOTIFY_CLIENT_SECRET")
        
        if required_configs:
            missing_configs = ", ".join(required_configs)
            raise ValueError(f"Missing required environment variables: {missing_configs}")


config = Config()

DEEPGRAM_API_KEY = config.DEEPGRAM_API_KEY
GROQ_API_KEY = config.GROQ_API_KEY
ELEVEN_LABS_API_KEY = config.ELEVEN_LABS_API_KEY

# Spotify configuration (optional)
SPOTIFY_CLIENT_ID = config.SPOTIFY_CLIENT_ID
SPOTIFY_CLIENT_SECRET = config.SPOTIFY_CLIENT_SECRET
SPOTIFY_REDIRECT_URI = config.SPOTIFY_REDIRECT_URI
