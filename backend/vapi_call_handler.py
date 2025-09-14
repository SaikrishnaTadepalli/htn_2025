import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
import httpx
from enum import Enum
import uuid

from vapi_agent_config import VAPIAgentConfig, ConversationMode, InterruptionBehavior
from joke_responder import JokeResponder
from spotify_responder import SpotifyResponder
from youtube_music_controller import YouTubeMusicController

logger = logging.getLogger(__name__)


class CallStatus(Enum):
    QUEUED = "queued"
    RINGING = "ringing"
    IN_PROGRESS = "in-progress"
    FORWARDING = "forwarding"
    ENDED = "ended"


class CallEndReason(Enum):
    HANGUP = "hangup"
    FUNCTION_HANGUP = "function-hangup"
    ASSISTANT_HANGUP = "assistant-hangup"
    CUSTOMER_HANGUP = "customer-hangup"
    ASSISTANT_ERROR = "assistant-error"
    EXCEEDED_MAX_DURATION = "exceeded-max-duration"
    SILENCE_TIMEOUT = "silence-timeout"
    MACHINE_DETECTION_TIMEOUT = "machine-detection-timeout"


@dataclass
class CallMetrics:
    call_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_seconds: int = 0
    total_messages: int = 0
    user_messages: int = 0
    assistant_messages: int = 0
    functions_called: int = 0
    interruptions: int = 0
    silence_periods: List[float] = field(default_factory=list)
    user_satisfaction: Optional[int] = None  # 1-5 rating
    technical_issues: List[str] = field(default_factory=list)


@dataclass
class ConversationMessage:
    role: str  # "user", "assistant", "function"
    content: str
    timestamp: datetime
    function_call: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class VAPICallHandler:
    def __init__(self,
                 vapi_token: str,
                 agent_config: VAPIAgentConfig,
                 joke_responder: Optional[JokeResponder] = None,
                 music_responder: Optional[SpotifyResponder] = None,
                 music_controller: Optional[YouTubeMusicController] = None):

        self.vapi_token = vapi_token
        self.agent_config = agent_config
        self.joke_responder = joke_responder
        self.music_responder = music_responder
        self.music_controller = music_controller

        # Call management
        self.active_calls: Dict[str, Dict[str, Any]] = {}
        self.call_metrics: Dict[str, CallMetrics] = {}
        self.conversation_history: Dict[str, List[ConversationMessage]] = {}

        # HTTP client for VAPI API calls
        self.client = httpx.AsyncClient(
            headers={
                "Authorization": f"Bearer {vapi_token}",
                "Content-Type": "application/json"
            },
            timeout=httpx.Timeout(30.0)
        )

        # Function handlers
        self.function_handlers = self._init_function_handlers()

        # Conversation flow settings
        self.max_conversation_length = 50  # Max messages before gentle wrap-up
        self.silence_threshold_ms = 5000   # When to prompt user after silence
        self.topic_change_cooldown = 30    # Seconds before suggesting topic change


    def _init_function_handlers(self) -> Dict[str, Callable]:
        """Initialize handlers for function calls from the AI agent"""
        return {
            "tell_joke": self._handle_joke_function,
            "play_music": self._handle_music_function,
            "change_personality": self._handle_personality_function,
            "analyze_mood": self._handle_mood_function,
            "remember_preference": self._handle_preference_function,
            "get_user_info": self._handle_user_info_function,
            "end_call": self._handle_end_call_function,
            "transfer_call": self._handle_transfer_function
        }


    async def create_phone_call(self,
                              phone_number: str,
                              customer_id: Optional[str] = None,
                              metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Create an outbound phone call using VAPI"""

        call_data = {
            "phoneNumber": phone_number,
            "assistantId": None,  # We'll use inline assistant config
            "assistant": self.agent_config.to_vapi_config(),
            "customer": {
                "id": customer_id or str(uuid.uuid4()),
                "numberE164CheckEnabled": True
            }
        }

        if metadata:
            call_data["metadata"] = metadata

        try:
            response = await self.client.post(
                "https://api.vapi.ai/call/phone",
                json=call_data
            )
            response.raise_for_status()

            call_result = response.json()
            call_id = call_result.get("id")

            if call_id:
                # Initialize call tracking
                self._init_call_tracking(call_id, phone_number, metadata)
                logger.info(f"Created phone call {call_id} to {phone_number}")

            return call_result

        except httpx.HTTPError as e:
            logger.error(f"Failed to create phone call: {e}")
            raise


    async def create_web_call(self,
                            assistant_overrides: Optional[Dict[str, Any]] = None,
                            metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Create a web call for browser-based conversations"""

        assistant_config = self.agent_config.to_vapi_config()
        if assistant_overrides:
            assistant_config.update(assistant_overrides)

        call_data = {
            "assistant": assistant_config,
            "customer": {
                "id": str(uuid.uuid4())
            }
        }

        if metadata:
            call_data["metadata"] = metadata

        try:
            response = await self.client.post(
                "https://api.vapi.ai/call/web",
                json=call_data
            )
            response.raise_for_status()

            call_result = response.json()
            call_id = call_result.get("id")

            if call_id:
                self._init_call_tracking(call_id, "web", metadata)
                logger.info(f"Created web call {call_id}")

            return call_result

        except httpx.HTTPError as e:
            logger.error(f"Failed to create web call: {e}")
            raise


    def _init_call_tracking(self, call_id: str, phone_number_or_type: str, metadata: Optional[Dict[str, Any]]):
        """Initialize tracking for a new call"""
        self.active_calls[call_id] = {
            "call_id": call_id,
            "phone_number": phone_number_or_type,
            "status": CallStatus.QUEUED,
            "start_time": datetime.now(),
            "metadata": metadata or {}
        }

        self.call_metrics[call_id] = CallMetrics(
            call_id=call_id,
            start_time=datetime.now()
        )

        self.conversation_history[call_id] = []


    async def handle_function_call(self, call_id: str, function_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Handle function calls from the AI agent during conversations"""

        logger.info(f"Handling function call '{function_name}' for call {call_id}: {parameters}")

        # Update metrics
        if call_id in self.call_metrics:
            self.call_metrics[call_id].functions_called += 1

        # Get handler
        handler = self.function_handlers.get(function_name)
        if not handler:
            logger.warning(f"No handler found for function: {function_name}")
            return {
                "success": False,
                "error": f"Function {function_name} not implemented",
                "result": "Sorry, I can't do that right now."
            }

        try:
            result = await handler(call_id, parameters)

            # Log function call in conversation history
            self._add_conversation_message(
                call_id,
                role="function",
                content=f"Called {function_name}",
                function_call={"name": function_name, "parameters": parameters},
                metadata={"result": result}
            )

            return result

        except Exception as e:
            logger.error(f"Error handling function {function_name}: {e}")
            return {
                "success": False,
                "error": str(e),
                "result": "Something went wrong with that request."
            }


    async def _handle_joke_function(self, call_id: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Handle joke requests through function calling"""
        if not self.joke_responder:
            return {"success": False, "result": "Joke service not available"}

        joke_type = parameters.get("joke_type", "sassy")
        topic = parameters.get("topic")

        try:
            # Get current conversation context
            conversation_context = None
            if call_id in self.conversation_history:
                recent_messages = self.conversation_history[call_id][-5:]
                conversation_text = " ".join([msg.content for msg in recent_messages])
                conversation_context = {"recent_conversation": conversation_text}

            # Generate joke using existing system
            joke_result = await self.joke_responder.process_text_for_joke(
                f"Tell me a {joke_type} joke" + (f" about {topic}" if topic else ""),
                conversation_context
            )

            if joke_result:
                return {
                    "success": True,
                    "result": joke_result["joke_response"],
                    "joke_type": joke_result.get("joke_type", joke_type),
                    "confidence": joke_result.get("confidence", 1.0)
                }
            else:
                return {
                    "success": False,
                    "result": "I'm fresh out of jokes right now. Maybe try asking me something else?"
                }

        except Exception as e:
            logger.error(f"Error generating joke: {e}")
            return {
                "success": False,
                "result": "My joke generator is having technical difficulties. The irony is not lost on me."
            }


    async def _handle_music_function(self, call_id: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Handle music requests through function calling"""
        if not self.music_responder or not self.music_controller:
            return {"success": False, "result": "Music service not available"}

        song_query = parameters.get("song_query", parameters.get("query", ""))
        mood = parameters.get("mood")

        try:
            # Parse the music request
            music_request = await self.music_responder.process_transcription(song_query)
            if not music_request:
                return {
                    "success": False,
                    "result": "I couldn't understand what music you want to play."
                }

            # Search and prepare music
            music_result = await self.music_controller.search_and_play(music_request)

            if music_result and music_result.get("success"):
                return {
                    "success": True,
                    "result": music_result.get("joke_message", f"Playing {music_request}"),
                    "track_info": music_result.get("track_info"),
                    "action": "music_queued"
                }
            else:
                return {
                    "success": False,
                    "result": f"Couldn't find '{song_query}'. Maybe try something that actually exists?"
                }

        except Exception as e:
            logger.error(f"Error handling music request: {e}")
            return {
                "success": False,
                "result": "Music service is having a moment. Try again later."
            }


    async def _handle_personality_function(self, call_id: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Handle personality changes during the call"""
        personality_type = parameters.get("personality_type", "sassy")
        duration_minutes = parameters.get("duration_minutes", 5)

        try:
            # Update agent config
            result = self.agent_config._handle_personality_change(personality_type, duration_minutes)

            # Schedule personality revert (simplified for demo)
            # In production, you'd use a proper task scheduler
            asyncio.create_task(self._revert_personality_after_delay(call_id, duration_minutes * 60))

            return {
                "success": True,
                "result": result["response"],
                "old_personality": result["old_personality"],
                "new_personality": result["new_personality"]
            }

        except Exception as e:
            logger.error(f"Error changing personality: {e}")
            return {
                "success": False,
                "result": "I can't seem to change my personality right now. Stuck being fabulous, I guess."
            }


    async def _handle_mood_function(self, call_id: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze user mood from conversation history"""
        conversation_history = parameters.get("conversation_history", [])

        if call_id in self.conversation_history and not conversation_history:
            # Use actual conversation history
            conversation_history = [msg.content for msg in self.conversation_history[call_id][-10:]]

        try:
            result = self.agent_config._handle_mood_analysis(conversation_history)
            return {
                "success": True,
                "result": result["response"],
                "detected_mood": result["detected_mood"],
                "confidence": result["confidence"]
            }

        except Exception as e:
            logger.error(f"Error analyzing mood: {e}")
            return {
                "success": False,
                "result": "I'm having trouble reading the room right now."
            }


    async def _handle_preference_function(self, call_id: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Store user preferences for future conversations"""
        preference_key = parameters.get("preference_key")
        preference_value = parameters.get("preference_value")

        if not preference_key or not preference_value:
            return {
                "success": False,
                "result": "I need both a preference type and value to remember that."
            }

        try:
            result = self.agent_config._handle_preference_storage(preference_key, preference_value)
            return {
                "success": True,
                "result": result["response"],
                "stored_preference": {preference_key: preference_value}
            }

        except Exception as e:
            logger.error(f"Error storing preference: {e}")
            return {
                "success": False,
                "result": "I'll try to remember that, but no promises."
            }


    async def _handle_user_info_function(self, call_id: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Get information about the current user/call"""
        info_type = parameters.get("info_type", "general")

        call_data = self.active_calls.get(call_id, {})
        metrics = self.call_metrics.get(call_id)

        if info_type == "call_duration" and metrics:
            duration = (datetime.now() - metrics.start_time).total_seconds()
            return {
                "success": True,
                "result": f"We've been chatting for {int(duration//60)} minutes and {int(duration%60)} seconds.",
                "duration_seconds": duration
            }
        elif info_type == "conversation_stats" and metrics:
            return {
                "success": True,
                "result": f"We've exchanged {metrics.total_messages} messages so far.",
                "total_messages": metrics.total_messages,
                "user_messages": metrics.user_messages,
                "assistant_messages": metrics.assistant_messages
            }
        else:
            return {
                "success": True,
                "result": "I'm here, you're there, we're talking. That's about all I know!",
                "call_id": call_id
            }


    async def _handle_end_call_function(self, call_id: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Handle call termination requests"""
        reason = parameters.get("reason", "Assistant initiated hangup")

        try:
            # End the call via VAPI
            await self.end_call(call_id)

            return {
                "success": True,
                "result": "Thanks for chatting! Catch you later!",
                "action": "end_call",
                "reason": reason
            }

        except Exception as e:
            logger.error(f"Error ending call: {e}")
            return {
                "success": False,
                "result": "I'm having trouble hanging up. Guess you're stuck with me!"
            }


    async def _handle_transfer_function(self, call_id: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Handle call transfer requests (placeholder for future implementation)"""
        destination = parameters.get("destination", "support")

        return {
            "success": False,
            "result": f"I'd transfer you to {destination} if I knew how. For now, you're stuck with me!",
            "action": "transfer_not_implemented"
        }


    async def _revert_personality_after_delay(self, call_id: str, delay_seconds: int):
        """Revert personality change after specified delay"""
        await asyncio.sleep(delay_seconds)

        if call_id in self.active_calls:
            # Revert to default personality
            self.agent_config.personality = self.agent_config.__class__().personality
            logger.info(f"Reverted personality for call {call_id}")


    def _add_conversation_message(self,
                                call_id: str,
                                role: str,
                                content: str,
                                function_call: Optional[Dict[str, Any]] = None,
                                metadata: Optional[Dict[str, Any]] = None):
        """Add a message to the conversation history"""
        message = ConversationMessage(
            role=role,
            content=content,
            timestamp=datetime.now(),
            function_call=function_call,
            metadata=metadata or {}
        )

        if call_id not in self.conversation_history:
            self.conversation_history[call_id] = []

        self.conversation_history[call_id].append(message)

        # Update metrics
        if call_id in self.call_metrics:
            metrics = self.call_metrics[call_id]
            metrics.total_messages += 1
            if role == "user":
                metrics.user_messages += 1
            elif role == "assistant":
                metrics.assistant_messages += 1


    async def handle_call_status_update(self, call_id: str, status: str, details: Dict[str, Any] = None):
        """Handle call status updates from webhooks"""
        if call_id not in self.active_calls:
            logger.warning(f"Received status update for unknown call: {call_id}")
            return

        self.active_calls[call_id]["status"] = CallStatus(status)

        if status == CallStatus.ENDED.value:
            await self._handle_call_ended(call_id, details or {})

        logger.info(f"Call {call_id} status updated to: {status}")


    async def _handle_call_ended(self, call_id: str, details: Dict[str, Any]):
        """Handle call completion"""
        if call_id in self.call_metrics:
            metrics = self.call_metrics[call_id]
            metrics.end_time = datetime.now()
            metrics.duration_seconds = int((metrics.end_time - metrics.start_time).total_seconds())

        # Log conversation summary
        conversation = self.conversation_history.get(call_id, [])
        logger.info(f"Call {call_id} ended. Total messages: {len(conversation)}")

        # Clean up active call (but keep metrics and history for analysis)
        self.active_calls.pop(call_id, None)


    async def get_call_metrics(self, call_id: str) -> Optional[CallMetrics]:
        """Get metrics for a specific call"""
        return self.call_metrics.get(call_id)


    async def get_conversation_history(self, call_id: str) -> List[ConversationMessage]:
        """Get conversation history for a specific call"""
        return self.conversation_history.get(call_id, [])


    async def end_call(self, call_id: str) -> bool:
        """End an active call"""
        try:
            response = await self.client.patch(
                f"https://api.vapi.ai/call/{call_id}",
                json={"status": "ended"}
            )
            response.raise_for_status()
            logger.info(f"Successfully ended call: {call_id}")
            return True

        except httpx.HTTPError as e:
            logger.error(f"Failed to end call {call_id}: {e}")
            return False


    async def close(self):
        """Clean up resources"""
        await self.client.aclose()