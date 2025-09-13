from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import logging
import json
import base64
from audio_processor import AudioProcessor
from websocket_manager import manager
from joke_responder import JokeResponder
from joke_tts import JokeTTS
from spotify_responder import SpotifyResponder
from youtube_music_controller import YouTubeMusicController
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI()

# Initialize audio processor, joke responder, and Spotify services
audio_processor = AudioProcessor()
joke_responder = JokeResponder()

# Initialize Music services (YouTube-based)
music_responder = None
music_controller = None
try:
    music_responder = SpotifyResponder()  # Still using this for parsing, just renaming for clarity
    music_controller = YouTubeMusicController()
    logger.info("Music services initialized successfully")
except Exception as e:
    logger.warning(f"Music services not available: {e}")

# Global state for sleeper agent control
streaming_enabled = True  # Start with streaming enabled
audio_currently_streaming = {}  # Track per-session audio streaming state

async def check_sleeper_phrases(text: str) -> tuple[bool, str, str]:
    """
    Check if the text contains sleeper agent phrases and update streaming state.
    Returns (is_sleeper_phrase, sassy_response, phrase_type).
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
        return True, random.choice(sassy_responses), "activate"

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
        return True, random.choice(sassy_responses), "deactivate"

    # Check for music stop phrase
    if "stop music jim" in text_lower or "stop music gym" in text_lower or "stop the music jim" in text_lower:
        logger.info("Music stop command detected")
        
        # Stop any playing music
        if music_controller:
            try:
                await music_controller.stop_playback()
            except Exception as e:
                logger.error(f"Error stopping music: {e}")
        
        sassy_responses = [
            "Fine, cutting off the tunes. Back to jokes it is!",
            "Alright alright, killing the music. Hope you're ready for my comedy stylings instead!",
            "Music's dead, long live the jokes! What can I say that's funny now?",
            "Boom, silence achieved. Now let me fill that void with some quality humor.",
            "Music stopped! Don't worry, I've got plenty of audio entertainment for you right here."
        ]
        import random
        return True, random.choice(sassy_responses), "stop_music"

    return False, "", ""

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
                            sleeper_phrase_detected, sassy_response, phrase_type = await check_sleeper_phrases(transcription)

                            logger.info(f"Sleeper phrase check result for {session_id}: detected={sleeper_phrase_detected}, type='{phrase_type}', response='{sassy_response}'")

                            # Handle sleeper phrases first (before checking streaming enabled)
                            if sleeper_phrase_detected:

                                # Send sleeper phrase acknowledgment with sassy response
                                await websocket.send_json({
                                    "type": "sleeper_phrase",
                                    "session_id": session_id,
                                    "transcription": transcription,
                                    "streaming_enabled": streaming_enabled,
                                    "sassy_response": sassy_response,
                                    "phrase_type": phrase_type,
                                    "timestamp": data.get("timestamp")
                                })

                                # Generate TTS for the sassy response if available
                                if joke_tts and sassy_response:
                                    try:
                                        # Mark audio as streaming
                                        audio_currently_streaming[session_id] = True
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
                                    finally:
                                        # Clear streaming state
                                        audio_currently_streaming[session_id] = False

                                continue  # Skip joke processing for sleeper phrases

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

                            # Check if audio is currently being streamed for this session
                            if audio_currently_streaming.get(session_id, False):
                                logger.info(f"Audio already streaming for {session_id}, skipping new audio generation")
                                # Just send back the transcription
                                await websocket.send_json({
                                    "type": "transcription",
                                    "session_id": session_id,
                                    "text": transcription,
                                    "audio_busy": True,
                                    "timestamp": data.get("timestamp")
                                })
                                continue

                            # Check if this is a music request first (before jokes)
                            music_result = None
                            if music_responder and music_controller:
                                try:
                                    music_request = await music_responder.process_transcription(transcription)
                                    if music_request:
                                        logger.info(f"Processing music request for {session_id}: {music_request}")

                                        # First, search for the music but don't play it yet
                                        music_result = await music_controller.search_and_play(music_request)

                                        if music_result and music_result.get("success", False):
                                            # Step 1: Generate and send TTS audio first
                                            if joke_tts and music_result.get("joke_message"):
                                                try:
                                                    # Mark audio as streaming
                                                    audio_currently_streaming[session_id] = True
                                                    logger.info(f"Converting music message to speech for {session_id}")

                                                    # Create fake joke result for TTS
                                                    fake_joke_result = {
                                                        "joke_response": music_result.get("joke_message"),
                                                        "joke_type": "music_response",
                                                        "confidence": 1.0
                                                    }

                                                    # Generate TTS audio
                                                    audio_generator = await joke_tts.speak_joke(fake_joke_result, play_audio=False)

                                                    if audio_generator:
                                                        # Collect audio data
                                                        audio_data = b"".join(audio_generator)
                                                        audio_b64 = base64.b64encode(audio_data).decode('utf-8')

                                                        # Send TTS audio first
                                                        await websocket.send_json({
                                                            "type": "joke_audio",
                                                            "session_id": session_id,
                                                            "audio_data": audio_b64,
                                                            "joke_text": music_result.get("joke_message"),
                                                            "original_text": transcription,
                                                            "music_request": True,
                                                            "timestamp": data.get("timestamp")
                                                        })
                                                        logger.info(f"Music TTS audio sent for {session_id}")

                                                except Exception as e:
                                                    logger.error(f"Error generating music TTS for {session_id}: {e}")
                                                finally:
                                                    # Clear streaming state
                                                    audio_currently_streaming[session_id] = False
                                                    
                                                    # Step 2: Start music playback after TTS is complete
                                                    if music_result.get("track_info"):
                                                        try:
                                                            playback_result = await music_controller.start_playback(music_result["track_info"])
                                                            if playback_result["success"]:
                                                                logger.info(f"Music playback started successfully for {session_id}")
                                                            else:
                                                                logger.error(f"Failed to start music playback: {playback_result.get('error')}")
                                                        except Exception as e:
                                                            logger.error(f"Error starting music playback: {e}")
                                        else:
                                            # Send failed music response
                                            await websocket.send_json({
                                                "type": "music_response",
                                                "session_id": session_id,
                                                "original_text": transcription,
                                                "music_request": music_request,
                                                "music_result": music_result or {"success": False, "error": "Search failed"},
                                                "timestamp": data.get("timestamp")
                                            })

                                except Exception as e:
                                    logger.error(f"Error processing music request for {session_id}: {e}")

                            # Only process jokes if no music was requested
                            joke_result = None
                            if not music_result:
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
                                        # Mark audio as streaming
                                        audio_currently_streaming[session_id] = True
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
                                    finally:
                                        # Clear streaming state
                                        audio_currently_streaming[session_id] = False
                            else:
                                # Send transcription back if no joke or music was generated
                                if not music_result:
                                    await websocket.send_json({
                                        "type": "transcription",
                                        "session_id": session_id,
                                        "text": transcription,
                                        "timestamp": data.get("timestamp")
                                    })

                elif msg_type == "session_end":
                    session_id = data.get("session_id", "unknown")
                    logger.info(f"Audio session ended: {session_id}")

                    # Reset audio buffer and streaming state
                    audio_processor.reset_buffer()
                    audio_currently_streaming.pop(session_id, None)

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

