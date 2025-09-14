import asyncio
import hmac
import hashlib
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.responses import JSONResponse
import json

from vapi_call_handler import VAPICallHandler, CallStatus, CallEndReason
from vapi_agent_config import VAPIAgentConfig

logger = logging.getLogger(__name__)


@dataclass
class WebhookEvent:
    event_type: str
    call_id: str
    timestamp: datetime
    data: Dict[str, Any]
    processed: bool = False
    retry_count: int = 0


@dataclass
class CallAnalytics:
    call_id: str
    phone_number: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration_seconds: int = 0
    end_reason: Optional[str] = None
    cost: float = 0.0
    transcript: List[Dict[str, Any]] = field(default_factory=list)
    function_calls: List[Dict[str, Any]] = field(default_factory=list)
    user_interruptions: int = 0
    ai_interruptions: int = 0
    silence_duration_total: float = 0.0
    user_sentiment_scores: List[float] = field(default_factory=list)
    technical_issues: List[str] = field(default_factory=list)


class VAPIWebhookServer:
    def __init__(self,
                 call_handler: VAPICallHandler,
                 webhook_secret: Optional[str] = None,
                 enable_analytics: bool = True):

        self.call_handler = call_handler
        self.webhook_secret = webhook_secret
        self.enable_analytics = enable_analytics

        # Event storage and processing
        self.pending_events: Dict[str, WebhookEvent] = {}
        self.call_analytics: Dict[str, CallAnalytics] = {}

        # FastAPI app for webhook endpoints
        self.app = FastAPI(title="VAPI Webhook Server", version="1.0.0")
        self._setup_routes()

        # Event processing settings
        self.max_retry_attempts = 3
        self.retry_delay_seconds = 5

        # Real-time event broadcasting (could integrate with WebSocket manager)
        self.event_subscribers: List[callable] = []


    def _setup_routes(self):
        """Setup FastAPI routes for webhook handling"""

        @self.app.post("/webhook/vapi")
        async def handle_vapi_webhook(request: Request, background_tasks: BackgroundTasks):
            """Main webhook endpoint for VAPI events"""
            try:
                # Get raw body for signature verification
                body = await request.body()

                # Verify webhook signature if secret is provided
                if self.webhook_secret:
                    signature = request.headers.get("x-vapi-signature")
                    if not signature or not self._verify_signature(body, signature):
                        raise HTTPException(status_code=401, detail="Invalid signature")

                # Parse JSON payload
                try:
                    payload = json.loads(body)
                except json.JSONDecodeError:
                    raise HTTPException(status_code=400, detail="Invalid JSON payload")

                # Extract event information
                event_type = payload.get("message", {}).get("type")
                call_id = payload.get("message", {}).get("call", {}).get("id")

                if not event_type or not call_id:
                    raise HTTPException(status_code=400, detail="Missing event type or call ID")

                logger.info(f"Received webhook event: {event_type} for call {call_id}")

                # Create webhook event
                webhook_event = WebhookEvent(
                    event_type=event_type,
                    call_id=call_id,
                    timestamp=datetime.now(),
                    data=payload
                )

                # Queue event for processing
                self.pending_events[f"{call_id}_{event_type}_{datetime.now().timestamp()}"] = webhook_event

                # Process event in background
                background_tasks.add_task(self._process_webhook_event, webhook_event)

                # Broadcast to subscribers
                await self._broadcast_event(webhook_event)

                return {"status": "received", "event_type": event_type, "call_id": call_id}

            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Error processing webhook: {e}")
                raise HTTPException(status_code=500, detail="Internal server error")


        @self.app.get("/webhook/status")
        async def get_webhook_status():
            """Get webhook server status and statistics"""
            return {
                "status": "active",
                "pending_events": len(self.pending_events),
                "active_calls": len(self.call_handler.active_calls),
                "total_analytics_records": len(self.call_analytics),
                "analytics_enabled": self.enable_analytics
            }


        @self.app.get("/analytics/call/{call_id}")
        async def get_call_analytics(call_id: str):
            """Get analytics for a specific call"""
            analytics = self.call_analytics.get(call_id)
            if not analytics:
                raise HTTPException(status_code=404, detail="Call analytics not found")

            return {
                "call_id": call_id,
                "analytics": analytics,
                "conversation_history": await self.call_handler.get_conversation_history(call_id),
                "call_metrics": await self.call_handler.get_call_metrics(call_id)
            }


        @self.app.get("/analytics/summary")
        async def get_analytics_summary():
            """Get summary analytics across all calls"""
            if not self.enable_analytics:
                raise HTTPException(status_code=404, detail="Analytics not enabled")

            total_calls = len(self.call_analytics)
            if total_calls == 0:
                return {"message": "No call analytics available"}

            # Calculate summary statistics
            total_duration = sum(a.duration_seconds for a in self.call_analytics.values())
            avg_duration = total_duration / total_calls if total_calls > 0 else 0

            total_cost = sum(a.cost for a in self.call_analytics.values())

            end_reasons = {}
            for analytics in self.call_analytics.values():
                reason = analytics.end_reason or "unknown"
                end_reasons[reason] = end_reasons.get(reason, 0) + 1

            sentiment_scores = []
            for analytics in self.call_analytics.values():
                sentiment_scores.extend(analytics.user_sentiment_scores)

            avg_sentiment = sum(sentiment_scores) / len(sentiment_scores) if sentiment_scores else 0

            return {
                "total_calls": total_calls,
                "total_duration_seconds": total_duration,
                "average_duration_seconds": round(avg_duration, 2),
                "total_cost": round(total_cost, 2),
                "average_cost_per_call": round(total_cost / total_calls, 2) if total_calls > 0 else 0,
                "end_reason_distribution": end_reasons,
                "average_user_sentiment": round(avg_sentiment, 2),
                "calls_with_technical_issues": sum(1 for a in self.call_analytics.values() if a.technical_issues)
            }


    def _verify_signature(self, payload: bytes, signature: str) -> bool:
        """Verify webhook signature using HMAC-SHA256"""
        if not self.webhook_secret:
            return True

        try:
            expected_signature = hmac.new(
                self.webhook_secret.encode('utf-8'),
                payload,
                hashlib.sha256
            ).hexdigest()

            return hmac.compare_digest(f"sha256={expected_signature}", signature)
        except Exception as e:
            logger.error(f"Error verifying signature: {e}")
            return False


    async def _process_webhook_event(self, event: WebhookEvent):
        """Process a webhook event based on its type"""
        try:
            event_type = event.event_type
            call_id = event.call_id
            data = event.data.get("message", {})

            logger.info(f"Processing {event_type} event for call {call_id}")

            # Route to appropriate handler
            if event_type == "call-start":
                await self._handle_call_start(call_id, data)
            elif event_type == "call-end":
                await self._handle_call_end(call_id, data)
            elif event_type == "transcript":
                await self._handle_transcript(call_id, data)
            elif event_type == "function-call":
                await self._handle_function_call_event(call_id, data)
            elif event_type == "speech-start":
                await self._handle_speech_start(call_id, data)
            elif event_type == "speech-end":
                await self._handle_speech_end(call_id, data)
            elif event_type == "conversation-update":
                await self._handle_conversation_update(call_id, data)
            elif event_type == "hang":
                await self._handle_hang(call_id, data)
            elif event_type == "status-update":
                await self._handle_status_update(call_id, data)
            else:
                logger.warning(f"Unknown event type: {event_type}")

            # Mark event as processed
            event.processed = True
            logger.info(f"Successfully processed {event_type} for call {call_id}")

        except Exception as e:
            logger.error(f"Error processing event {event.event_type} for call {event.call_id}: {e}")
            await self._retry_event_processing(event, str(e))


    async def _handle_call_start(self, call_id: str, data: Dict[str, Any]):
        """Handle call start events"""
        call_data = data.get("call", {})

        # Initialize analytics if enabled
        if self.enable_analytics:
            self.call_analytics[call_id] = CallAnalytics(
                call_id=call_id,
                phone_number=call_data.get("customer", {}).get("number"),
                start_time=datetime.now()
            )

        # Update call handler
        await self.call_handler.handle_call_status_update(call_id, CallStatus.IN_PROGRESS.value, call_data)

        logger.info(f"Call {call_id} started")


    async def _handle_call_end(self, call_id: str, data: Dict[str, Any]):
        """Handle call end events"""
        call_data = data.get("call", {})
        end_reason = call_data.get("endedReason")
        cost = call_data.get("cost", 0)

        # Update analytics
        if self.enable_analytics and call_id in self.call_analytics:
            analytics = self.call_analytics[call_id]
            analytics.end_time = datetime.now()
            analytics.end_reason = end_reason
            analytics.cost = cost

            if analytics.start_time:
                analytics.duration_seconds = int((analytics.end_time - analytics.start_time).total_seconds())

        # Update call handler
        await self.call_handler.handle_call_status_update(call_id, CallStatus.ENDED.value, call_data)

        logger.info(f"Call {call_id} ended. Reason: {end_reason}, Cost: ${cost}")


    async def _handle_transcript(self, call_id: str, data: Dict[str, Any]):
        """Handle transcript events (speech-to-text results)"""
        transcript_data = data.get("transcript", {})
        role = transcript_data.get("role")  # "user" or "assistant"
        text = transcript_data.get("transcript", "")
        timestamp = transcript_data.get("timestamp")

        # Store transcript in analytics
        if self.enable_analytics and call_id in self.call_analytics:
            self.call_analytics[call_id].transcript.append({
                "role": role,
                "text": text,
                "timestamp": timestamp
            })

        # Add to conversation history
        self.call_handler._add_conversation_message(
            call_id=call_id,
            role=role,
            content=text,
            metadata={"timestamp": timestamp, "source": "transcript"}
        )

        logger.debug(f"Transcript for {call_id} - {role}: {text}")


    async def _handle_function_call_event(self, call_id: str, data: Dict[str, Any]):
        """Handle function call webhook events"""
        function_call_data = data.get("functionCall", {})
        function_name = function_call_data.get("name")
        parameters = function_call_data.get("parameters", {})

        # Store in analytics
        if self.enable_analytics and call_id in self.call_analytics:
            self.call_analytics[call_id].function_calls.append({
                "name": function_name,
                "parameters": parameters,
                "timestamp": datetime.now().isoformat()
            })

        # Process the function call
        result = await self.call_handler.handle_function_call(call_id, function_name, parameters)

        logger.info(f"Function call {function_name} processed for {call_id}: {result}")

        return result


    async def _handle_speech_start(self, call_id: str, data: Dict[str, Any]):
        """Handle speech start events (user or AI started speaking)"""
        role = data.get("role", "unknown")

        # Track interruptions in analytics
        if self.enable_analytics and call_id in self.call_analytics:
            if role == "user":
                self.call_analytics[call_id].user_interruptions += 1
            elif role == "assistant":
                self.call_analytics[call_id].ai_interruptions += 1

        logger.debug(f"Speech started for {call_id} - {role}")


    async def _handle_speech_end(self, call_id: str, data: Dict[str, Any]):
        """Handle speech end events"""
        role = data.get("role", "unknown")
        duration = data.get("duration", 0)

        logger.debug(f"Speech ended for {call_id} - {role}, duration: {duration}ms")


    async def _handle_conversation_update(self, call_id: str, data: Dict[str, Any]):
        """Handle conversation update events"""
        # This could include sentiment analysis, topic changes, etc.
        conversation_data = data.get("conversation", {})

        # Extract sentiment if available
        sentiment = conversation_data.get("sentiment")
        if sentiment and self.enable_analytics and call_id in self.call_analytics:
            self.call_analytics[call_id].user_sentiment_scores.append(sentiment)

        logger.debug(f"Conversation update for {call_id}: {conversation_data}")


    async def _handle_hang(self, call_id: str, data: Dict[str, Any]):
        """Handle hang/disconnect events"""
        reason = data.get("reason", "unknown")

        if self.enable_analytics and call_id in self.call_analytics:
            if reason not in ["normal_hangup", "completed"]:
                self.call_analytics[call_id].technical_issues.append(f"Unexpected hang: {reason}")

        logger.info(f"Hang event for {call_id}: {reason}")


    async def _handle_status_update(self, call_id: str, data: Dict[str, Any]):
        """Handle general status update events"""
        status = data.get("status")
        details = data.get("details", {})

        await self.call_handler.handle_call_status_update(call_id, status, details)

        logger.info(f"Status update for {call_id}: {status}")


    async def _retry_event_processing(self, event: WebhookEvent, error_message: str):
        """Retry processing a failed event"""
        if event.retry_count < self.max_retry_attempts:
            event.retry_count += 1

            logger.warning(f"Retrying event processing for {event.event_type} (attempt {event.retry_count}): {error_message}")

            # Wait before retry
            await asyncio.sleep(self.retry_delay_seconds * event.retry_count)

            try:
                await self._process_webhook_event(event)
            except Exception as retry_error:
                logger.error(f"Retry failed for {event.event_type}: {retry_error}")

                if event.retry_count >= self.max_retry_attempts:
                    logger.error(f"Max retries exceeded for event {event.event_type}. Giving up.")
        else:
            logger.error(f"Max retries exceeded for event {event.event_type}. Marking as failed.")


    async def _broadcast_event(self, event: WebhookEvent):
        """Broadcast event to all subscribers"""
        for subscriber in self.event_subscribers:
            try:
                if asyncio.iscoroutinefunction(subscriber):
                    await subscriber(event)
                else:
                    subscriber(event)
            except Exception as e:
                logger.error(f"Error broadcasting event to subscriber: {e}")


    def subscribe_to_events(self, callback: callable):
        """Subscribe to real-time webhook events"""
        self.event_subscribers.append(callback)
        logger.info("New event subscriber added")


    def unsubscribe_from_events(self, callback: callable):
        """Unsubscribe from webhook events"""
        if callback in self.event_subscribers:
            self.event_subscribers.remove(callback)
            logger.info("Event subscriber removed")


    async def cleanup_old_data(self, days_to_keep: int = 30):
        """Clean up old analytics data to prevent memory issues"""
        cutoff_date = datetime.now() - datetime.timedelta(days=days_to_keep)

        # Clean up old analytics
        old_call_ids = [
            call_id for call_id, analytics in self.call_analytics.items()
            if analytics.end_time and analytics.end_time < cutoff_date
        ]

        for call_id in old_call_ids:
            self.call_analytics.pop(call_id, None)
            self.call_handler.conversation_history.pop(call_id, None)
            self.call_handler.call_metrics.pop(call_id, None)

        # Clean up processed events
        processed_events = [
            event_id for event_id, event in self.pending_events.items()
            if event.processed and event.timestamp < cutoff_date
        ]

        for event_id in processed_events:
            self.pending_events.pop(event_id, None)

        logger.info(f"Cleaned up {len(old_call_ids)} old call records and {len(processed_events)} processed events")


    async def get_real_time_metrics(self) -> Dict[str, Any]:
        """Get real-time metrics for monitoring"""
        active_calls = len(self.call_handler.active_calls)

        # Calculate metrics from recent calls (last hour)
        recent_cutoff = datetime.now() - datetime.timedelta(hours=1)
        recent_calls = [
            analytics for analytics in self.call_analytics.values()
            if analytics.start_time and analytics.start_time > recent_cutoff
        ]

        return {
            "timestamp": datetime.now().isoformat(),
            "active_calls": active_calls,
            "recent_calls_count": len(recent_calls),
            "pending_events": len(self.pending_events),
            "average_recent_duration": sum(c.duration_seconds for c in recent_calls) / len(recent_calls) if recent_calls else 0,
            "recent_cost": sum(c.cost for c in recent_calls),
            "error_rate": len([e for e in self.pending_events.values() if e.retry_count > 0]) / max(len(self.pending_events), 1)
        }