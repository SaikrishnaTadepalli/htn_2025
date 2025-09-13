import asyncio
import logging
import os
from typing import Optional, Dict, Any
from groq import Groq
import json
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)

class JokeResponder:
    """
    A class that listens to socket messages and uses Groq models to decide
    whether to respond with jokes or funny quips based on the input text.
    """
    
    def __init__(self, groq_api_key: Optional[str] = None):
        """
        Initialize the JokeResponder with Groq API key.
        
        Args:
            groq_api_key: Groq API key. If None, will try to get from environment variable GROQ_API_KEY
        """
        self.groq_api_key = groq_api_key or os.getenv("GROQ_API_KEY")
        if not self.groq_api_key:
            raise ValueError("Groq API key is required. Set GROQ_API_KEY environment variable or pass it directly.")
        
        self.client = Groq(api_key=self.groq_api_key)
        self.model = "llama-3.1-8b-instant"  # Using a current model for better joke generation
        
        # Configuration for joke response criteria
        self.joke_threshold = 0.7  # Threshold for deciding to respond with a joke
        self.max_response_length = 200  # Maximum length of joke response
        
    async def should_respond_with_joke(self, text: str) -> Dict[str, Any]:
        """
        Analyze the input text to determine if it's worth responding with a joke.
        
        Args:
            text: The input text to analyze
            
        Returns:
            Dict containing decision, confidence, and reasoning
        """
        try:
            prompt = f"""
            Analyze the following text and determine if it would be appropriate to respond with a joke or funny quip.
            
            Consider:
            1. Is the text asking a question or making a statement that could benefit from humor?
            2. Is the context appropriate for a lighthearted response?
            3. Would a joke add value to the conversation?
            4. Is the text too serious or sensitive for humor?
            
            Text: "{text}"
            
            Respond with a JSON object containing:
            - "should_respond": boolean (true if worth responding with a joke)
            - "confidence": float (0.0 to 1.0, how confident you are)
            - "reasoning": string (brief explanation of your decision)
            - "joke_type": string (suggested type of joke: "pun", "observational", "wordplay", "situational", or "none")
            """
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=300
            )
            
            result_text = response.choices[0].message.content.strip()
            
            # Clean up the response - remove markdown code blocks if present
            if result_text.startswith("```json"):
                result_text = result_text[7:]  # Remove ```json
            if result_text.startswith("```"):
                result_text = result_text[3:]   # Remove ```
            if result_text.endswith("```"):
                result_text = result_text[:-3]  # Remove trailing ```
            
            result_text = result_text.strip()
            
            # Extract JSON from the response - look for the first complete JSON object
            json_start = result_text.find('{')
            if json_start != -1:
                # Find the matching closing brace
                brace_count = 0
                json_end = json_start
                for i, char in enumerate(result_text[json_start:], json_start):
                    if char == '{':
                        brace_count += 1
                    elif char == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            json_end = i + 1
                            break
                
                if brace_count == 0:  # Found complete JSON
                    result_text = result_text[json_start:json_end]
            
            # Try to parse JSON response
            try:
                result = json.loads(result_text)
                return result
            except json.JSONDecodeError:
                # Fallback if JSON parsing fails
                logger.warning(f"Failed to parse JSON response: {result_text}")
                return {
                    "should_respond": False,
                    "confidence": 0.0,
                    "reasoning": "Failed to parse AI response",
                    "joke_type": "none"
                }
                
        except Exception as e:
            logger.error(f"Error analyzing text for joke response: {e}")
            return {
                "should_respond": False,
                "confidence": 0.0,
                "reasoning": f"Error occurred: {str(e)}",
                "joke_type": "none"
            }
    
    async def generate_joke_response(self, text: str, joke_type: str = "general") -> Optional[str]:
        """
        Generate a joke or funny quip based on the input text.
        
        Args:
            text: The input text to respond to
            joke_type: Type of joke to generate
            
        Returns:
            Generated joke response or None if generation fails
        """
        try:
            prompt = f"""
            Generate a funny, appropriate joke or quip in response to the following text.
            
            Guidelines:
            - Keep it lighthearted and appropriate
            - Make it relevant to the input text
            - Keep it under {self.max_response_length} characters
            - Be clever but not offensive
            - Use the joke type: {joke_type}
            
            Input text: "{text}"
            
            Generate a funny response:
            """
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.8,  # Higher temperature for more creative responses
                max_tokens=150
            )
            
            joke_response = response.choices[0].message.content.strip()
            
            # Clean up the response
            joke_response = joke_response.replace('"', '').replace("'", "")
            
            if len(joke_response) > self.max_response_length:
                joke_response = joke_response[:self.max_response_length] + "..."
            
            return joke_response
            
        except Exception as e:
            logger.error(f"Error generating joke response: {e}")
            return None
    
    async def process_text_for_joke(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Main method to process text and determine if a joke response should be generated.
        
        Args:
            text: The input text to process
            
        Returns:
            Dict with joke response data or None if no joke should be generated
        """
        if not text or len(text.strip()) < 3:
            return None
        
        # Analyze if we should respond with a joke
        analysis = await self.should_respond_with_joke(text)
        
        if not analysis.get("should_respond", False):
            logger.info(f"Not responding with joke for: '{text}' - {analysis.get('reasoning', 'No reason provided')}")
            return None
        
        confidence = analysis.get("confidence", 0.0)
        if confidence < self.joke_threshold:
            logger.info(f"Confidence too low ({confidence}) for joke response to: '{text}'")
            return None
        
        # Generate the joke response
        joke_type = analysis.get("joke_type", "general")
        joke_response = await self.generate_joke_response(text, joke_type)
        
        if not joke_response:
            logger.warning(f"Failed to generate joke response for: '{text}'")
            return None
        
        return {
            "original_text": text,
            "joke_response": joke_response,
            "joke_type": joke_type,
            "confidence": confidence,
            "reasoning": analysis.get("reasoning", ""),
            "timestamp": asyncio.get_event_loop().time()
        }
    
    async def handle_websocket_message(self, message_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Handle a WebSocket message and potentially generate a joke response.
        
        Args:
            message_data: The WebSocket message data
            
        Returns:
            Joke response data or None
        """
        try:
            # Extract text from different message types
            text = None
            
            if message_data.get("type") == "transcription":
                text = message_data.get("text", "")
            elif message_data.get("type") == "text_message":
                text = message_data.get("content", "")
            elif "text" in message_data:
                text = message_data["text"]
            elif "content" in message_data:
                text = message_data["content"]
            
            if not text:
                return None
            
            # Process the text for potential joke response
            return await self.process_text_for_joke(text)
            
        except Exception as e:
            logger.error(f"Error handling WebSocket message: {e}")
            return None

# Example usage and testing
async def test_joke_responder():
    """Test function for the JokeResponder class."""
    try:
        # Initialize with API key from environment
        responder = JokeResponder()
        
        # Test cases
        test_texts = [
            "What's the weather like today?",
            "I'm feeling really sad about my job.",
            "Why did the chicken cross the road?",
            "Can you help me with this math problem?",
            "I love pizza!",
            "My computer is broken again."
        ]
        
        for text in test_texts:
            print(f"\nTesting: '{text}'")
            result = await responder.process_text_for_joke(text)
            
            if result:
                print(f"✅ Joke Response: {result['joke_response']}")
                print(f"   Type: {result['joke_type']}, Confidence: {result['confidence']:.2f}")
            else:
                print("❌ No joke response generated")
                
    except Exception as e:
        print(f"Test failed: {e}")

if __name__ == "__main__":
    # Run test if executed directly
    asyncio.run(test_joke_responder())
