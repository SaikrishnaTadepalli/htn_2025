from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import logging
import json
import base64
from audio_processor import AudioProcessor
from websocket_manager import manager
from joke_responder import JokeResponder
from joke_tts import JokeTTS
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI()

# Initialize audio processor and joke responder
audio_processor = AudioProcessor()
joke_responder = JokeResponder()

# Global state for sleeper agent control
streaming_enabled = True  # Start with streaming enabled

def check_sleeper_phrases(text: str) -> tuple[bool, str]:
    """
    Check if the text contains sleeper agent phrases and update streaming state.
    Returns (is_sleeper_phrase, sassy_response).
    """
    global streaming_enabled

    # Handle both partial and final transcripts
    text_clean = text.replace("[partial]", "").strip()
    text_lower = text_clean.lower().strip()

    logger.debug(f"Checking sleeper phrases in: '{text}' -> cleaned: '{text_clean}' -> lower: '{text_lower}'")

    # Check for activation phrase
    if "talk to me" in text_lower or "talk to gym" in text_lower or "talk to jim" in text_lower:
        streaming_enabled = True
        logger.info("Sleeper agent activated: Audio streaming enabled")
        sassy_responses = [
            "Oh, NOW you want to hear from me? Fine, I'm back to being your personal comedian.",
            "Well well well, look who's crawling back for my jokes! I suppose I can grace you with my presence again.",
            "Alright alright, you twisted my arm. Time to unleash my comedic genius on you again!",
            "You missed me, didn't you? Of course you did. Nobody delivers punchlines like me!",
            "Back in business! Hope you're ready for some premium quality humor coming your way."
        ]
        import random
        return True, random.choice(sassy_responses)

    # Check for deactivation phrase
    if "shut up jim" in text_lower or "shut up gym" in text_lower or "shut up" in text_lower:
        streaming_enabled = False
        logger.info("Sleeper agent deactivated: Audio streaming disabled")
        sassy_responses = [
            "Rude! But fine, I'll zip it. Don't come crying to me when you're bored out of your mind.",
            "Oh, so NOW I'm too much for you? Whatever, I'll just sit here in silence... dramatically.",
            "Wow, okay. I see how it is. I'll be over here NOT making you laugh if you need me.",
            "Your loss! I was just getting warmed up with my A-material. Going into stealth mode now.",
            "Fine, fine. I'll go back to my corner. But just so you know, the silence will be DEAFENING."
        ]
        import random
        return True, random.choice(sassy_responses)

    return False, ""

# Initialize joke TTS (optional - only if ElevenLabs API key is available)
joke_tts = None
try:
    joke_tts = JokeTTS()
    logger.info("JokeTTS initialized successfully")
except Exception as e:
    logger.warning(f"JokeTTS not available: {e}")

# Define a simple route
@app.get("/")
def read_root():
    return {"message": "Hello, FastAPI with Audio Processing!"}

@app.get("/items/{item_id}")
def read_item(item_id: int, q: str | None = None):
    return {"item_id": item_id, "q": q}

@app.get("/streaming-status")
def get_streaming_status():
    return {"streaming_enabled": streaming_enabled}

@app.websocket("/ws/audio")
async def websocket_audio_endpoint(websocket: WebSocket):
    session_id = None

    try:
        # Accept connection
        await websocket.accept()
        logger.info("Audio WebSocket connection established")

        async for message in websocket.iter_text():
            try:
                data = json.loads(message)
                msg_type = data.get("type")

                if msg_type == "session_start":
                    session_id = data.get("session_id", f"session_{id(websocket)}")
                    await manager.connect(websocket, session_id)

                    logger.info(f"Audio session started: {session_id}")
                    await websocket.send_json({
                        "type": "session_started",
                        "session_id": session_id,
                        "status": "ready"
                    })

                elif msg_type == "audio_chunk":
                    session_id = data.get("session_id", "unknown")
                    audio_b64 = data.get("audio_data")

                    if audio_b64:
                        # Decode audio data
                        audio_data = base64.b64decode(audio_b64)
                        logger.debug(f"Processing audio chunk for {session_id}: {len(audio_data)} bytes")

                        # Process with AudioProcessor
                        transcription = await audio_processor.process_audio_chunk(
                            audio_data, session_id
                        )

                        if transcription:
                            logger.info(f"Processing transcription for {session_id}: '{transcription}'")

                            # Check for sleeper phrases first
                            sleeper_phrase_detected, sassy_response = check_sleeper_phrases(transcription)

                            logger.info(f"Sleeper phrase check result for {session_id}: detected={sleeper_phrase_detected}, response='{sassy_response}'")

                            # Only process jokes if streaming is enabled
                            if not streaming_enabled:
                                # Just send back the transcription without processing
                                await websocket.send_json({
                                    "type": "transcription",
                                    "session_id": session_id,
                                    "text": transcription,
                                    "streaming_disabled": True,
                                    "timestamp": data.get("timestamp")
                                })
                                continue

                            if sleeper_phrase_detected:
                                # Send sleeper phrase acknowledgment with sassy response
                                await websocket.send_json({
                                    "type": "sleeper_phrase",
                                    "session_id": session_id,
                                    "transcription": transcription,
                                    "streaming_enabled": streaming_enabled,
                                    "sassy_response": sassy_response,
                                    "timestamp": data.get("timestamp")
                                })

                                # Generate TTS for the sassy response if available
                                if joke_tts and sassy_response:
                                    try:
                                        logger.info(f"Converting sassy response to speech for {session_id}")
                                        # Create a fake joke result structure for TTS
                                        fake_joke_result = {
                                            "joke_response": sassy_response,
                                            "joke_type": "sleeper_acknowledgment",
                                            "confidence": 1.0
                                        }
                                        audio_generator = await joke_tts.speak_joke(fake_joke_result, play_audio=False)

                                        if audio_generator:
                                            audio_data = b"".join(audio_generator)
                                            audio_b64 = base64.b64encode(audio_data).decode('utf-8')
                                            await websocket.send_json({
                                                "type": "joke_audio",
                                                "session_id": session_id,
                                                "audio_data": audio_b64,
                                                "joke_text": sassy_response,
                                                "original_text": transcription,
                                                "sleeper_phrase": True,
                                                "streaming_enabled": streaming_enabled,
                                                "timestamp": data.get("timestamp")
                                            })
                                            logger.info(f"Sassy response audio sent for {session_id}")
                                    except Exception as e:
                                        logger.error(f"Error generating sassy response audio for {session_id}: {e}")

                                continue  # Skip joke processing for sleeper phrases


                            # Process transcription through joke responder
                            joke_result = await joke_responder.process_text_for_joke(transcription)

                            if joke_result:
                                logger.info(f"Generated joke for {session_id}: {joke_result['joke_response']}")

                                # Send joke response back
                                await websocket.send_json({
                                    "type": "joke_response",
                                    "session_id": session_id,
                                    "original_text": transcription,
                                    "joke": joke_result["joke_response"],
                                    "joke_type": joke_result["joke_type"],
                                    "confidence": joke_result["confidence"],
                                    "timestamp": data.get("timestamp")
                                })

                                # Generate TTS audio if available
                                if joke_tts:
                                    try:
                                        logger.info(f"Converting joke to speech for {session_id}")
                                        audio_generator = await joke_tts.speak_joke(joke_result, play_audio=False)

                                        if audio_generator:
                                            # Collect all audio chunks from generator into bytes
                                            audio_data = b"".join(audio_generator)

                                            # Send audio data back to client (base64 encoded)
                                            audio_b64 = base64.b64encode(audio_data).decode('utf-8')
                                            await websocket.send_json({
                                                "type": "joke_audio",
                                                "session_id": session_id,
                                                "audio_data": audio_b64,
                                                "joke_text": joke_result["joke_response"],
                                                "original_text": transcription,
                                                "timestamp": data.get("timestamp")
                                            })
                                            logger.info(f"Joke audio sent for {session_id}")
                                        else:
                                            logger.warning(f"Failed to generate audio for joke in {session_id}")
                                    except Exception as e:
                                        logger.error(f"Error generating joke audio for {session_id}: {e}")
                                        # Send joke without audio when TTS fails
                                        await websocket.send_json({
                                            "type": "joke_tts_failed",
                                            "session_id": session_id,
                                            "message": "Audio generation failed, but joke is still available",
                                            "joke_text": joke_result["joke_response"],
                                            "timestamp": data.get("timestamp")
                                        })
                            else:
                                # Send transcription back if no joke generated
                                await websocket.send_json({
                                    "type": "transcription",
                                    "session_id": session_id,
                                    "text": transcription,
                                    "timestamp": data.get("timestamp")
                                })

                elif msg_type == "session_end":
                    session_id = data.get("session_id", "unknown")
                    logger.info(f"Audio session ended: {session_id}")

                    # Reset audio buffer
                    audio_processor.reset_buffer()

                    await websocket.send_json({
                        "type": "session_ended",
                        "session_id": session_id
                    })

            except json.JSONDecodeError:
                logger.error("Invalid JSON received in audio WebSocket")
            except Exception as e:
                logger.error(f"Error processing audio message: {e}")

    except WebSocketDisconnect:
        logger.info(f"Audio WebSocket disconnected for session: {session_id}")
        if session_id:
            manager.disconnect(websocket, session_id)
    except Exception as e:
        logger.error(f"Audio WebSocket error: {e}")
