
import asyncio
import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass, field
from dotenv import load_dotenv

from deepgram import DeepgramClient, DeepgramClientOptions, LiveTranscriptionEvents
from deepgram.clients.live.v1 import LiveOptions

from config import DEEPGRAM_API_KEY

load_dotenv()
logger = logging.getLogger(__name__)


@dataclass
class DGSession:
    dg_connection: Any
    latest_transcript: Optional[str] = None
    active: bool = True
    last_sent_at: float = 0.0
    keepalive_task: Optional[asyncio.Task] = None


class AudioProcessor:
    """
    Streams audio chunks to Deepgram and exposes the latest transcript as a simple string.
    Returns partial strings (prefixed with "[partial] ") and final strings when available.
    """

    def __init__(self):
        self.sample_rate: int = 16000
        self.channels: int = 1
        self.encoding: str = "linear16"   # 16-bit PCM little-endian
        self.keepalive_after_s: float = 8.0  # send silence if no audio for this many seconds

        if not DEEPGRAM_API_KEY:
            raise RuntimeError("DEEPGRAM_API_KEY is not set")
        logger.info(f"Initializing Deepgram client with API key: {DEEPGRAM_API_KEY[:10]}...")
        self._dg_client = DeepgramClient(
            config=DeepgramClientOptions(api_key=DEEPGRAM_API_KEY)
        )

        self.sessions: Dict[str, DGSession] = {}


    async def process_audio_chunk(self, audio_data: bytes, session_id: str) -> Optional[str]:
        try:
            session = await self._get_or_create_session(session_id)
            if not session or not session.active or not session.dg_connection:
                logger.debug("Deepgram session not ready for %s", session_id)
                return None

            # Send bytes to Deepgram
            logger.debug(f"Sending {len(audio_data)} bytes to Deepgram for {session_id}")
            session.dg_connection.send(audio_data)
            session.last_sent_at = asyncio.get_event_loop().time()
            logger.debug(f"Audio data sent to Deepgram for {session_id}")

            # Opportunistically start keepalive task if not already running
            if session.keepalive_task is None:
                session.keepalive_task = asyncio.create_task(self._keepalive_loop(session_id))

            # Read any newly arrived transcript
            logger.debug(f"Latest transcript for {session_id}: {session.latest_transcript}")
            if session.latest_transcript:
                text = session.latest_transcript
                session.latest_transcript = None
                logger.debug(f"Returning transcript for {session_id}: {text}")
                return text

        except Exception as e:
            logger.exception("Error processing audio chunk for %s: %s", session_id, e)
            await self._cleanup_session(session_id)

        return None

    async def end_session(self, session_id: str) -> None:
        """Call this when you're done streaming for a given session."""
        await self._cleanup_session(session_id)

    def reset_buffer(self):
        """Reset any internal buffers. Called when session ends."""
        # For this implementation, we don't have persistent buffers to reset
        # But we keep this method for compatibility with the main.py call
        pass

    async def _get_or_create_session(self, session_id: str) -> Optional[DGSession]:
        # Return existing if active
        sess = self.sessions.get(session_id)
        if sess and sess.active and sess.dg_connection:
            return sess

        # Otherwise (re)create
        return await self._create_session(session_id)

    async def _create_session(self, session_id: str) -> Optional[DGSession]:
        try:
            # Create a WebSocket live connection (SDK v3+)
            dg_conn = self._dg_client.listen.websocket.v("1")

            sess = DGSession(dg_connection=dg_conn)

            # Register event handlers that close over `sess` and `session_id`
            def _on_transcript(_conn, result, **kwargs):
                try:
                    alt = result.channel.alternatives[0] if result.channel.alternatives else None
                    if not alt or not alt.transcript:
                        logger.debug(f"No transcript in alternatives for {session_id}")
                        return
                    text = alt.transcript.strip()
                    if not text:
                        logger.debug(f"Empty transcript for {session_id}")
                        return
                    if getattr(result, "is_final", False):
                        sess.latest_transcript = text
                        logger.info("Final transcript [%s]: %s", session_id, text)
                    else:
                        sess.latest_transcript = f"[partial] {text}"
                        logger.debug("Partial transcript [%s]: %s", session_id, text)
                except Exception as e:
                    logger.exception("Transcript handler error [%s]: %s", session_id, e)

            def _on_utt_end(_conn, **kwargs):
                logger.debug("UtteranceEnd [%s]: %s", session_id, kwargs)

            def _on_error(_conn, error, **kwargs):
                logger.error("Deepgram error [%s]: %s", session_id, error)

            def _on_close(_conn, **kwargs):
                logger.info("Deepgram closed [%s]: %s", session_id, kwargs)
                sess.active = False

            # Register the handlers
            dg_conn.on(LiveTranscriptionEvents.Transcript, _on_transcript)
            dg_conn.on(LiveTranscriptionEvents.UtteranceEnd, _on_utt_end)
            dg_conn.on(LiveTranscriptionEvents.Error, _on_error)
            dg_conn.on(LiveTranscriptionEvents.Close, _on_close)

            # Start the stream with recommended, low-latency options
            options = LiveOptions(
                # Model/language
                model="nova-3",
                language="en-US",

                # Audio format
                encoding=self.encoding,
                channels=self.channels,
                sample_rate=self.sample_rate,

                # Results behavior
                interim_results=True,   # get partials
                smart_format=True,      # punctuation, capitalization, etc.
                vad_events=True,
                utterance_end_ms=1000,  # finalize about 1s after silence
                endpointing=300,        # micro-segmentation to speed finals
                no_delay=True,          # prefer immediacy over formatting latency
            )

            logger.info(f"Starting Deepgram connection with options: {options}")
            if not dg_conn.start(options):
                logger.error("Failed to start Deepgram connection for session: %s", session_id)
                return None

            # Track new session
            self.sessions[session_id] = sess
            logger.info("Started Deepgram connection for session: %s", session_id)
            return sess

        except Exception as e:
            logger.exception("Failed to create Deepgram session for %s: %s", session_id, e)
            return None

    async def _cleanup_session(self, session_id: str) -> None:
        sess = self.sessions.get(session_id)
        if not sess:
            return
        try:
            # Stop keepalive
            if sess.keepalive_task:
                sess.keepalive_task.cancel()
                try:
                    await sess.keepalive_task
                except asyncio.CancelledError:
                    pass
                sess.keepalive_task = None

            # Finish Deepgram stream
            if sess.dg_connection:
                try:
                    sess.dg_connection.finish()
                except Exception:
                    logger.exception("Error closing Deepgram connection for %s", session_id)
            sess.active = False
        finally:
            self.sessions.pop(session_id, None)
            logger.info("Cleaned up Deepgram session: %s", session_id)

    async def _keepalive_loop(self, session_id: str) -> None:
        """
        Sends a tiny silence frame if no audio has been sent for `keepalive_after_s`.
        Helps avoid idle socket closes during long pauses.
        """
        try:
            while True:
                await asyncio.sleep(1.0)
                sess = self.sessions.get(session_id)
                if not sess or not sess.active or not sess.dg_connection:
                    return
                now = asyncio.get_event_loop().time()
                if (now - sess.last_sent_at) >= self.keepalive_after_s:
                    # ~10ms of silence at 16kHz mono, 16-bit PCM = 160 samples * 2 bytes
                    silence = b"\x00\x00" * 160
                    try:
                        sess.dg_connection.send(silence)
                        # Don't spam; only update timestamp modestly
                        sess.last_sent_at = now
                        logger.debug("Keepalive silence sent for session: %s", session_id)
                    except Exception:
                        logger.exception("Keepalive send failed for %s", session_id)
                        return
        except asyncio.CancelledError:
            # normal on cleanup
            return
