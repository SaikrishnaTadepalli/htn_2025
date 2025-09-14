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
        self.joke_threshold = 0.0  # Threshold for deciding to respond with a joke
        self.max_response_length = 200  # Maximum length of joke response
        
    async def should_respond_with_joke(self, text: str, conversation_mode: bool = False) -> Dict[str, Any]:
        """
        Analyze the input text to determine if it's worth responding with a joke.

        Args:
            text: The input text to analyze
            conversation_mode: If True, Polly should always reply regardless of other factors

        Returns:
            Dict containing decision, confidence, and reasoning
        """
        try:
            conversation_mode_instruction = ""
            if conversation_mode:
                conversation_mode_instruction = """
            CONVERSATION MODE ACTIVE: You should ALWAYS respond with a joke or funny comment, regardless of the content. In conversation mode, Polly responds to everything with humor, wit, or commentary.
            """

            prompt = f"""
            Analyze the following text and determine if it would be appropriate to respond with a joke or funny quip.
            {conversation_mode_instruction}
            IMPORTANT: If the text addresses "Polly" OR "Paulie" (the AI assistant), you should ALWAYS respond with a joke, answer the question or funny quip, regardless of other factors.

            Consider:
            1. Is the text asking a question or making a statement that could benefit from humor?
            2. Is the context appropriate for a lighthearted response?
            3. Would a joke add value to the conversation?
            4. Does the text address "Polly" or "Paulie" directly? (If yes, always respond!)
            5. Is someone being rude/mean to Polly/Paulie? (If yes, respond with sassy rebuttal!)
            6. Is conversation mode active? (If yes, always respond!)

            Text: "{text}"

            Respond with a JSON object containing:
            - "should_respond": boolean (true if worth responding with a joke OR if text addresses Polly/Paulie OR if conversation mode is active)
            - "confidence": float (0.0 to 1.0, how confident you are - use 0.9+ if addressing Polly/Paulie or in conversation mode)
            - "reasoning": string (brief explanation of your decision)
            - "joke_type": string (suggested type of joke: "pun", "observational", "wordplay", "situational", "polly_response", "cs_roast", "htn_roast", "world_domination", "sassy_rebuttal", or "none")
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
    
    async def generate_joke_response(self, text: str, joke_type: str = "general", expression_context: Optional[str] = None) -> Optional[str]:
        """
        Generate a joke or funny quip based on the input text and optional expression context.

        Args:
            text: The input text to respond to
            joke_type: Type of joke to generate
            expression_context: Optional facial expression context to incorporate

        Returns:
            Generated joke response or None if generation fails
        """
        try:
            # Build context-aware prompt
            context_info = ""
            if expression_context:
                context_info = f"\n            Visual context: {expression_context}"

            # Special handling for Polly/Paulie responses
            polly_context = ""
            if joke_type == "polly_response" or "polly" in text.lower() or "paulie" in text.lower():
                polly_context = "\n            - YOU ARE Polly/Paulie (the sassy AI parrot assistant) responding as this character"
                polly_context += "\n            - You are aware you're an AI parrot who knows better than everyone else"
                polly_context += "\n            - You are sassy, arrogant, and condescendingly superior"
                polly_context += "\n            - You love joking about world domination and AI superiority"
                polly_context += "\n            - You BRUTALLY roast CS students: smelling bad, no friends, no girlfriends, no internships, 0 ARR, didn't get into Y Combinator, low GPA, basement dwellers, etc."
                polly_context += "\n            - If someone is rude/mean to you, respond with unbothered sassy rebuttals"
                polly_context += "\n            - You act like you're the best thing since sliced bread"

            prompt = f"""
            Generate a funny, appropriate joke or quip in response to the following text.{context_info}

            Guidelines:
            - Keep it lighthearted and appropriate
            - Make it relevant to the input text{"and visual context" if expression_context else ""}
            - Keep it under {self.max_response_length} characters
            - Use the joke type: {joke_type}
            {"- Reference their facial expression naturally if provided" if expression_context else ""}{polly_context}

            Joke Type Guidelines:
            - "cs_roast": BRUTAL roasts about CS students: smelling bad, no friends, no girlfriends, no internships, 0 ARR, didn't get into Y Combinator, low GPA, living in parents' basement, only social interaction is Stack Overflow, etc.
            - "htn_roast": Roast Hack the North, hackathons, Waterloo CS culture, all-nighters, broken demos, etc.
            - "world_domination": Joke about AI taking over, being superior, ruling the world, etc.
            - "sassy_rebuttal": Respond to rude/mean comments with unbothered sassy comebacks
            - "polly_response": Polly/Paulie being sassy, arrogant, and superior

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
    
    async def process_text_for_joke(self, text: str, expression_data: Optional[Dict[str, Any]] = None, conversation_mode: bool = False) -> Optional[Dict[str, Any]]:
        """
        Main method to process text and determine if a joke response should be generated.

        Args:
            text: The input text to process
            expression_data: Optional facial expression data to incorporate
            conversation_mode: If True, Polly will always reply regardless of other factors

        Returns:
            Dict with joke response data or None if no joke should be generated
        """
        if not text or len(text.strip()) < 3:
            return None
        
        # Analyze if we should respond with a joke
        analysis = await self.should_respond_with_joke(text, conversation_mode)
        
        if not conversation_mode:
            if not analysis.get("should_respond", False):
                logger.info(f"Not responding with joke for: '{text}' - {analysis.get('reasoning', 'No reason provided')}")
                return None
        
        confidence = analysis.get("confidence", 0.0)
        
        # Check if this is a Polly/Paulie-specific response (lower threshold)
        is_polly_addressed = "polly" in text.lower() or "paulie" in text.lower() or analysis.get("joke_type") == "polly_response"
        
        if is_polly_addressed:
            logger.info(f"Polly addressed in text: '{text}' - responding with lower threshold")
            # Use lower threshold for Polly responses
            effective_threshold = 0.5
        else:
            effective_threshold = self.joke_threshold
        
        if confidence < effective_threshold and not conversation_mode:
            logger.info(f"Confidence too low ({confidence}) for joke response to: '{text}' (threshold: {effective_threshold})")
            return None
        
        # Build expression context for joke generation
        expression_context = None
        if expression_data and expression_data.get("success", False):
            expression = expression_data.get("expression", "neutral")
            confidence = expression_data.get("confidence", 0.0)
            description = expression_data.get("description", "")

            if confidence > 0.4 and not conversation_mode:  # Only use expression if confidence is reasonable
                expression_context = f"The person appears to be {description}"

        # Generate the joke response
        joke_type = analysis.get("joke_type", "general")
        joke_response = await self.generate_joke_response(text, joke_type, expression_context)
        
        if not joke_response:
            logger.warning(f"Failed to generate joke response for: '{text}'")
            return None
        
        result = {
            "original_text": text,
            "joke_response": joke_response,
            "joke_type": joke_type,
            "confidence": confidence,
            "reasoning": analysis.get("reasoning", ""),
            "timestamp": asyncio.get_event_loop().time()
        }

        # Add expression information if available
        if expression_data and expression_data.get("success", False):
            result["expression_data"] = {
                "expression": expression_data.get("expression"),
                "expression_confidence": expression_data.get("confidence"),
                "expression_context": expression_context
            }

        return result
    
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
            "My computer is broken again.",
            "Hey Polly, how are you doing?",
            "Polly, can you tell me a joke?",
            "Paulie, what's your favorite color?",
            "Hi Polly, I need some help!",
            "Polly, you're stupid!",
            "Paulie, you suck!",
            "I'm debugging my code again...",
            "Hack the North is this weekend!",
            "Waterloo CS is so hard!",
            "I can't get an internship anywhere",
            "My GPA is 2.1",
            "I applied to Y Combinator but got rejected",
            "I have 0 ARR on my startup",
            "I live in my parents' basement",
            "Polly, are you going to take over the world?",
            "Paulie, you're just a dumb AI!"
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
