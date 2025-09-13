import asyncio
import logging
import os
from typing import Optional, Dict, Any
from groq import Groq
import json
from dotenv import load_dotenv
from config import GROQ_API_KEY, ELEVEN_LABS_API_KEY

load_dotenv()

logger = logging.getLogger(__name__)

class SpotifyResponder:
    """
    A class that listens to transcriptions and uses Groq to detect and parse
    music-related requests, then formats them for Spotify API consumption.
    """

    def __init__(self):
        """
        Initialize the SpotifyResponder with Groq API key.

        Args:
            groq_api_key: Groq API key. If None, will try to get from environment variable GROQ_API_KEY
        """
        self.groq_api_key = GROQ_API_KEY
        self.eleven_labs_api_key = ELEVEN_LABS_API_KEY
        if not self.groq_api_key:
            raise ValueError("Groq API key is required. Set GROQ_API_KEY environment variable or pass it directly.")

        self.client = Groq(api_key=self.groq_api_key)
        self.model = "llama-3.1-8b-instant"

        # Keywords that indicate music-related requests
        self.music_keywords = [
            "play", "music", "song", "track", "album", "artist", "spotify",
            "listen", "hear", "sound", "tune", "sing", "band", "musician"
        ]

    def is_music_request(self, text: str) -> bool:
        """
        Check if the transcription contains music-related keywords.

        Args:
            text: The transcribed text to analyze

        Returns:
            bool: True if text appears to be a music request
        """
        text_lower = text.lower().replace("[partial]", "").strip()

        # Check for music keywords
        has_music_keyword = any(keyword in text_lower for keyword in self.music_keywords)

        # Also check for common patterns
        music_patterns = [
            "put on", "turn on", "start", "queue up", "blast",
            "throw on", "crank up", "fire up"
        ]
        has_music_pattern = any(pattern in text_lower for pattern in music_patterns)

        return has_music_keyword or has_music_pattern

    async def parse_music_request(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Use Groq to parse natural language music request into structured data.

        Args:
            text: The transcribed music request

        Returns:
            Dict containing parsed music request data or None if parsing failed
        """
        try:
            # Clean the text
            clean_text = text.replace("[partial]", "").strip()

            prompt = f"""
            Parse this music request and extract the information: "{clean_text}"

            You must respond with ONLY a valid JSON object with these exact fields:
            - "artist": The artist name if mentioned (string or null)
            - "song": The song/track name if mentioned (string or null) 
            - "album": The album name if mentioned (string or null)
            - "action": Always "play" (string)
            - "confidence": How confident you are in the extraction (0.0-1.0)

            Examples of correct responses:
            "play michael jackson" → {{"artist": "Michael Jackson", "song": null, "album": null, "action": "play", "confidence": 0.9}}
            "play billie jean by michael jackson" → {{"artist": "Michael Jackson", "song": "Billie Jean", "album": null, "action": "play", "confidence": 0.95}}
            "put on some taylor swift music" → {{"artist": "Taylor Swift", "song": null, "album": null, "action": "play", "confidence": 0.8}}

            IMPORTANT: Respond with ONLY the JSON object. Do not include any code, explanations, or other text. Just the raw JSON.
            """

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a music request parser. Extract artist, song, and album information from natural language requests. You MUST respond with ONLY valid JSON - no code, no explanations, no markdown formatting. Just raw JSON."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_tokens=150,
                temperature=0.1
            )

            if response.choices and response.choices[0].message:
                content = response.choices[0].message.content.strip()
                logger.info(f"Groq response for music parsing: {content}")

                # Clean up the content - remove markdown code blocks if present
                if content.startswith("```") and content.endswith("```"):
                    lines = content.split('\n')
                    content = '\n'.join(lines[1:-1])  # Remove first and last lines
                elif content.startswith("```json"):
                    content = content[7:]  # Remove ```json
                    if content.endswith("```"):
                        content = content[:-3]  # Remove trailing ```
                
                content = content.strip()
                logger.info(f"Cleaned Groq response: {content}")

                # Try to parse JSON
                try:
                    parsed_data = json.loads(content)

                    # Validate required fields
                    if not isinstance(parsed_data, dict):
                        logger.warning("Groq returned non-dict response")
                        return None

                    # Ensure we have at least artist or song
                    if not parsed_data.get("artist") and not parsed_data.get("song"):
                        logger.info("No artist or song extracted from music request")
                        return None

                    # Add metadata
                    parsed_data["original_text"] = clean_text
                    parsed_data["timestamp"] = asyncio.get_event_loop().time()

                    logger.info(f"Successfully parsed music request: {parsed_data}")
                    return parsed_data

                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse Groq JSON response: {e}")
                    logger.error(f"Response content: {content}")
                    return None

        except Exception as e:
            logger.error(f"Error parsing music request with Groq: {e}")
            return None

        return None

    async def process_transcription(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Main method to process a transcription and determine if it's a music request.

        Args:
            text: The transcribed text to process

        Returns:
            Dict containing music request data if successful, None otherwise
        """
        try:
            # First check if it looks like a music request
            if not self.is_music_request(text):
                logger.debug(f"Text doesn't appear to be a music request: {text}")
                return None

            logger.info(f"Detected potential music request: {text}")

            # Parse the request with Groq
            parsed_request = await self.parse_music_request(text)

            if parsed_request:
                logger.info(f"Successfully processed music request: {parsed_request}")
                return parsed_request
            else:
                logger.info(f"Failed to parse music request: {text}")
                return None

        except Exception as e:
            logger.error(f"Error processing transcription: {e}")
            return None