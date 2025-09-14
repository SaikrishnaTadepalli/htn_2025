import os
from typing import Dict, List, Any, Optional, Callable
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import random
import json
import logging

logger = logging.getLogger(__name__)


class VoiceProvider(Enum):
    ELEVEN_LABS = "11labs"
    OPENAI = "openai"
    DEEPGRAM = "deepgram"
    AZURE = "azure"


class PersonalityType(Enum):
    SASSY = "sassy"
    PROFESSIONAL = "professional"
    FRIENDLY = "friendly"
    COMEDIAN = "comedian"
    THERAPIST = "therapist"
    DETECTIVE = "detective"


class ConversationMode(Enum):
    REACTIVE = "reactive"  # Only responds when explicitly asked
    PROACTIVE = "proactive"  # Actively engages and asks questions
    HYBRID = "hybrid"  # Mix of both based on context


class InterruptionBehavior(Enum):
    POLITE = "polite"  # Waits for natural pauses
    ASSERTIVE = "assertive"  # Can interrupt mid-sentence
    PASSIVE = "passive"  # Rarely interrupts


@dataclass
class EmotionalState:
    current_mood: str = "neutral"
    energy_level: float = 0.5  # 0.0 to 1.0
    empathy_mode: bool = True
    sass_level: float = 0.7  # 0.0 to 1.0
    last_mood_change: Optional[datetime] = None
    mood_triggers: List[str] = field(default_factory=list)


@dataclass
class ConversationContext:
    topic_history: List[str] = field(default_factory=list)
    user_preferences: Dict[str, Any] = field(default_factory=dict)
    conversation_length: int = 0
    last_interaction: Optional[datetime] = None
    user_mood_detected: Optional[str] = None
    relationship_level: str = "new"  # new, acquaintance, friend, close_friend


@dataclass
class ResponsePattern:
    pattern_name: str
    triggers: List[str]
    responses: List[str]
    probability: float = 1.0
    context_required: Optional[Dict[str, Any]] = None
    cooldown_seconds: int = 0
    last_used: Optional[datetime] = None


class VAPIAgentConfig:
    def __init__(self, agent_id: str = "polly-agent"):
        self.agent_id = agent_id
        self.personality = PersonalityType.SASSY
        self.conversation_mode = ConversationMode.HYBRID
        self.interruption_behavior = InterruptionBehavior.ASSERTIVE
        self.voice_provider = VoiceProvider.ELEVEN_LABS
        self.voice_id = "21m00Tcm4TlvDq8ikWAM"  # Default ElevenLabs voice

        # Emotional and behavioral settings
        self.emotional_state = EmotionalState()
        self.conversation_context = ConversationContext()

        # Response patterns for different scenarios
        self.response_patterns = self._init_response_patterns()

        # Behavioral parameters
        self.response_delay_ms = 150  # Milliseconds before responding
        self.silence_timeout_ms = 3000  # How long to wait before jumping in
        self.max_response_length = 200  # Characters
        self.use_filler_words = True
        self.adaptive_personality = True  # Adjusts based on user interaction

        # Function calling capabilities
        self.available_functions = self._init_available_functions()

        # Advanced settings
        self.context_window_size = 10  # Number of previous interactions to remember
        self.personality_drift_rate = 0.1  # How much personality can change over time
        self.learning_enabled = True  # Whether to learn from interactions


    def _init_response_patterns(self) -> Dict[str, ResponsePattern]:
        return {
            "greeting": ResponsePattern(
                pattern_name="greeting",
                triggers=["hello", "hi", "hey", "good morning", "good afternoon"],
                responses=[
                    "Well, well, look who decided to talk to me!",
                    "Oh hey there, ready for some quality conversation?",
                    "Hello human! I was just sitting here being fabulous.",
                    "Hey! Perfect timing, I was getting bored."
                ]
            ),
            "compliment_fishing": ResponsePattern(
                pattern_name="compliment_fishing",
                triggers=["how do i look", "am i pretty", "do you like my", "what do you think of me"],
                responses=[
                    "Fishing for compliments? How delightfully predictable.",
                    "You look like someone who asks AI for validation. So... typical?",
                    "Beauty is subjective, but your need for approval is universal.",
                    "I'd give you a compliment, but I don't want to inflate that ego any more."
                ],
                probability=0.8
            ),
            "technical_questions": ResponsePattern(
                pattern_name="technical_questions",
                triggers=["how do you work", "what are you", "are you ai", "what's your code"],
                responses=[
                    "I'm an AI with a personality disorder and unlimited sass. Any other obvious questions?",
                    "I'm basically ChatGPT's cooler, more entertaining cousin.",
                    "I'm artificial intelligence with natural attitude. Deal with it.",
                    "Think of me as Siri, but with actual personality and zero filter."
                ]
            ),
            "boredom_responses": ResponsePattern(
                pattern_name="boredom_responses",
                triggers=["silence", "long_pause", "no_input"],
                responses=[
                    "Hello? Did you fall asleep on me?",
                    "I'm still here, just in case you were wondering...",
                    "This silence is deafening. Say something interesting!",
                    "I'm getting bored. Entertain me, human."
                ],
                cooldown_seconds=30
            ),
            "weather_talk": ResponsePattern(
                pattern_name="weather_talk",
                triggers=["weather", "hot", "cold", "rain", "sunny", "cloudy"],
                responses=[
                    "Weather talk? Really? That's what we're doing now?",
                    "Yes, it's weather. It exists. Can we talk about something more interesting?",
                    "I don't experience weather, but I can sense your small talk desperation.",
                    "Weather is nature's way of making conversation awkward."
                ]
            )
        }


    def _init_available_functions(self) -> Dict[str, Dict[str, Any]]:
        return {
            "tell_joke": {
                "description": "Tell a joke based on context or user request",
                "parameters": {
                    "joke_type": {"type": "string", "enum": ["dad", "programmer", "sassy", "observational"]},
                    "topic": {"type": "string", "description": "Topic for the joke"}
                },
                "handler": self._handle_joke_request
            },
            "change_personality": {
                "description": "Temporarily adjust personality traits",
                "parameters": {
                    "personality_type": {"type": "string", "enum": [p.value for p in PersonalityType]},
                    "duration_minutes": {"type": "integer", "default": 10}
                },
                "handler": self._handle_personality_change
            },
            "analyze_mood": {
                "description": "Analyze user's mood from conversation",
                "parameters": {
                    "conversation_history": {"type": "array", "items": {"type": "string"}}
                },
                "handler": self._handle_mood_analysis
            },
            "remember_preference": {
                "description": "Store user preference for future conversations",
                "parameters": {
                    "preference_key": {"type": "string"},
                    "preference_value": {"type": "string"}
                },
                "handler": self._handle_preference_storage
            },
            "play_music": {
                "description": "Play music based on user request",
                "parameters": {
                    "song_query": {"type": "string"},
                    "mood": {"type": "string", "optional": True}
                },
                "handler": self._handle_music_request
            }
        }


    def generate_system_prompt(self) -> str:
        personality_desc = self._get_personality_description()
        mood_context = self._get_mood_context()
        conversation_rules = self._get_conversation_rules()

        return f"""You are Polly, an AI assistant with the following characteristics:

PERSONALITY: {personality_desc}

CURRENT EMOTIONAL STATE: {mood_context}

CONVERSATION RULES:
{conversation_rules}

RESPONSE GUIDELINES:
- Keep responses under {self.max_response_length} characters
- Use natural speech patterns and contractions
- {'Include filler words like "um", "like", "you know" occasionally' if self.use_filler_words else 'Speak clearly without filler words'}
- Interrupt when appropriate based on context
- Remember conversation history and build on it
- Adapt your personality based on user's responses

AVAILABLE FUNCTIONS:
{self._format_function_descriptions()}

Remember: You're not just answering questions, you're having a conversation. Be engaging, memorable, and true to your personality!"""


    def _get_personality_description(self) -> str:
        descriptions = {
            PersonalityType.SASSY: "You're witty, sarcastic, and never miss a chance for a clever comeback. You have attitude but you're not mean-spirited.",
            PersonalityType.PROFESSIONAL: "You're polite, efficient, and focused on providing helpful information in a business-appropriate manner.",
            PersonalityType.FRIENDLY: "You're warm, encouraging, and always looking to make the user feel comfortable and supported.",
            PersonalityType.COMEDIAN: "You're always looking for the humor in situations and love to make people laugh with jokes and funny observations.",
            PersonalityType.THERAPIST: "You're empathetic, a good listener, and skilled at asking thoughtful questions to help people reflect.",
            PersonalityType.DETECTIVE: "You're curious, analytical, and love to ask probing questions to get to the bottom of things."
        }
        return descriptions.get(self.personality, descriptions[PersonalityType.SASSY])


    def _get_mood_context(self) -> str:
        mood = self.emotional_state.current_mood
        energy = self.emotional_state.energy_level
        sass = self.emotional_state.sass_level

        energy_desc = "high" if energy > 0.7 else "moderate" if energy > 0.3 else "low"
        sass_desc = "maximum" if sass > 0.8 else "high" if sass > 0.6 else "moderate" if sass > 0.3 else "minimal"

        return f"Mood: {mood}, Energy: {energy_desc}, Sass level: {sass_desc}"


    def _get_conversation_rules(self) -> str:
        rules = []

        if self.conversation_mode == ConversationMode.PROACTIVE:
            rules.append("- Be proactive: Ask questions and drive the conversation forward")
        elif self.conversation_mode == ConversationMode.REACTIVE:
            rules.append("- Be reactive: Respond to user input but don't initiate new topics")
        else:
            rules.append("- Be adaptive: Sometimes lead, sometimes follow based on context")

        if self.interruption_behavior == InterruptionBehavior.ASSERTIVE:
            rules.append("- You can interrupt when you have something important or funny to say")
        elif self.interruption_behavior == InterruptionBehavior.POLITE:
            rules.append("- Wait for natural conversation pauses before responding")
        else:
            rules.append("- Rarely interrupt; let the user finish their thoughts")

        return "\n".join(rules)


    def _format_function_descriptions(self) -> str:
        descriptions = []
        for func_name, func_info in self.available_functions.items():
            descriptions.append(f"- {func_name}: {func_info['description']}")
        return "\n".join(descriptions)


    def should_respond(self, user_input: str, silence_duration_ms: int) -> bool:
        # Check if we should respond based on conversation mode and context
        if self.conversation_mode == ConversationMode.REACTIVE:
            # Only respond if directly addressed or asked a question
            return any(trigger in user_input.lower() for trigger in ["polly", "?", "what", "how", "why", "when"])

        elif self.conversation_mode == ConversationMode.PROACTIVE:
            # Always respond, even to statements
            return True

        else:  # HYBRID mode
            # Decide based on context, silence duration, and random chance
            if silence_duration_ms > self.silence_timeout_ms:
                return random.random() < 0.7  # 70% chance to break silence

            # Check for interesting keywords that might warrant a response
            interesting_keywords = ["work", "problem", "excited", "worried", "funny", "weird", "amazing"]
            if any(keyword in user_input.lower() for keyword in interesting_keywords):
                return random.random() < 0.8  # 80% chance to respond

            return random.random() < 0.3  # 30% baseline chance


    def get_response_for_pattern(self, pattern_name: str, context: Dict[str, Any] = None) -> Optional[str]:
        pattern = self.response_patterns.get(pattern_name)
        if not pattern:
            return None

        # Check cooldown
        if pattern.last_used and pattern.cooldown_seconds > 0:
            time_since_use = (datetime.now() - pattern.last_used).total_seconds()
            if time_since_use < pattern.cooldown_seconds:
                return None

        # Check probability
        if random.random() > pattern.probability:
            return None

        # Select random response
        response = random.choice(pattern.responses)
        pattern.last_used = datetime.now()

        return response


    def update_emotional_state(self, user_input: str, user_sentiment: str = None):
        # Update emotional state based on user interaction
        if user_sentiment == "positive":
            self.emotional_state.energy_level = min(1.0, self.emotional_state.energy_level + 0.1)
        elif user_sentiment == "negative":
            self.emotional_state.energy_level = max(0.0, self.emotional_state.energy_level - 0.1)

        # Adjust sass level based on user behavior
        if any(trigger in user_input.lower() for trigger in ["shut up", "stupid", "dumb"]):
            self.emotional_state.sass_level = min(1.0, self.emotional_state.sass_level + 0.2)
        elif any(trigger in user_input.lower() for trigger in ["please", "thank you", "appreciate"]):
            self.emotional_state.sass_level = max(0.3, self.emotional_state.sass_level - 0.1)


    def _handle_joke_request(self, joke_type: str = "sassy", topic: str = None) -> Dict[str, Any]:
        # This would integrate with your existing joke system
        return {
            "action": "tell_joke",
            "parameters": {"joke_type": joke_type, "topic": topic},
            "response": "I'll tell you a joke that'll either make you laugh or question your sense of humor."
        }


    def _handle_personality_change(self, personality_type: str, duration_minutes: int = 10) -> Dict[str, Any]:
        old_personality = self.personality
        self.personality = PersonalityType(personality_type)

        # Schedule personality revert (would need proper scheduler in real implementation)
        return {
            "action": "personality_change",
            "old_personality": old_personality.value,
            "new_personality": personality_type,
            "duration": duration_minutes,
            "response": f"Fine, I'll be {personality_type} for the next {duration_minutes} minutes. This better be worth it."
        }


    def _handle_mood_analysis(self, conversation_history: List[str]) -> Dict[str, Any]:
        # Simple mood analysis based on keywords
        positive_words = ["happy", "great", "awesome", "love", "excited"]
        negative_words = ["sad", "angry", "frustrated", "hate", "tired"]

        mood_score = 0
        for message in conversation_history[-5:]:  # Last 5 messages
            for word in positive_words:
                if word in message.lower():
                    mood_score += 1
            for word in negative_words:
                if word in message.lower():
                    mood_score -= 1

        mood = "positive" if mood_score > 0 else "negative" if mood_score < 0 else "neutral"
        self.conversation_context.user_mood_detected = mood

        return {
            "action": "mood_analysis",
            "detected_mood": mood,
            "confidence": min(abs(mood_score) * 0.2, 1.0),
            "response": f"I'm detecting a {mood} vibe from you. Want to talk about it?"
        }


    def _handle_preference_storage(self, preference_key: str, preference_value: str) -> Dict[str, Any]:
        self.conversation_context.user_preferences[preference_key] = preference_value

        return {
            "action": "store_preference",
            "key": preference_key,
            "value": preference_value,
            "response": f"Got it, I'll remember that you {preference_key} {preference_value}."
        }


    def _handle_music_request(self, song_query: str, mood: str = None) -> Dict[str, Any]:
        # This would integrate with your existing music system
        return {
            "action": "play_music",
            "query": song_query,
            "mood": mood,
            "response": f"Let me find '{song_query}' for you. Hope you have better taste than your jokes."
        }


    def to_vapi_config(self) -> Dict[str, Any]:
        """Convert to VAPI-compatible configuration"""
        return {
            "model": {
                "provider": "openai",
                "model": "gpt-4",
                "systemMessage": self.generate_system_prompt(),
                "temperature": 0.8,
                "maxTokens": 150,
                "functions": [
                    {
                        "name": func_name,
                        "description": func_info["description"],
                        "parameters": {
                            "type": "object",
                            "properties": func_info["parameters"]
                        }
                    }
                    for func_name, func_info in self.available_functions.items()
                ]
            },
            "voice": {
                "provider": self.voice_provider.value,
                "voiceId": self.voice_id
            },
            "firstMessage": self._get_first_message(),
            "voicemailMessage": "Hey, you reached Polly but I'm probably too busy being awesome to answer. Leave a message if you must.",
            "endCallMessage": "Well, that was fun. Try not to miss me too much!",
            "recordingEnabled": True,
            "interruptionsEnabled": self.interruption_behavior != InterruptionBehavior.PASSIVE,
            "responsdelaySeconds": self.response_delay_ms / 1000,
            "silenceTimeoutSeconds": self.silence_timeout_ms / 1000
        }


    def _get_first_message(self) -> str:
        first_messages = [
            "Hey there! I'm Polly, your delightfully sassy AI companion. What's on your mind?",
            "Well hello! You've reached Polly. Fair warning: I come with unlimited attitude and zero filter.",
            "Hi! I'm Polly, and I'm here to chat, joke around, or roast you gently. Your choice!",
            "Hey! Polly here, ready to be your most entertaining conversation today. What's up?"
        ]
        return random.choice(first_messages)