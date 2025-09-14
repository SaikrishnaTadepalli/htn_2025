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
from facial_expression_analyzer import FacialExpressionAnalyzer
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI()

# Initialize audio processor, joke responder, facial expression analyzer, and services
audio_processor = AudioProcessor()
joke_responder = JokeResponder()

# Initialize facial expression analyzer (optional - gracefully handle initialization errors)
expression_analyzer = None
try:
    expression_analyzer = FacialExpressionAnalyzer()
    logger.info("Facial expression analyzer initialized successfully")
except Exception as e:
    logger.warning(f"Facial expression analyzer not available: {e}")

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
conversation_mode = True  # Track whether Polly is in conversation mode (always replies) or comment mode (evaluates whether to reply)

# Expression data cache for each session
expression_cache = {}  # Store recent expression data per session

async def stream_joke_audio(websocket, session_id, joke_data, joke_tts, joke_type="general", original_text="", extra_data=None):
    """Helper function to stream joke audio chunks to client"""
    try:
        # Get audio stream generator for low latency
        audio_stream = await joke_tts.speak_joke(joke_data, play_audio=False, stream=True)
        if not audio_stream:
            return False

        logger.info(f"Starting TTS stream for {joke_type} joke: {joke_data.get('joke_response', '')}")

        # Send joke response immediately
        response_data = {
            "type": "joke_response",
            "session_id": session_id,
            "joke_text": joke_data.get("joke_response", ""),
            "original_text": original_text,
            "joke_type": joke_type,
            "streaming": True,
            "timestamp": extra_data.get("timestamp") if extra_data else None
        }

        # Add any extra data
        if extra_data:
            response_data.update(extra_data)

        await websocket.send_json(response_data)

        # Stream audio chunks as they arrive
        chunk_count = 0
        for audio_chunk in audio_stream:
            chunk_b64 = base64.b64encode(audio_chunk).decode('utf-8')
            await websocket.send_json({
                "type": "joke_audio_chunk",
                "session_id": session_id,
                "chunk_data": chunk_b64,
                "chunk_index": chunk_count,
                "format": "mp3"
            })
            chunk_count += 1

        # Send end marker
        await websocket.send_json({
            "type": "joke_audio_end",
            "session_id": session_id,
            "total_chunks": chunk_count
        })

        logger.info(f"Completed TTS stream for {joke_type}: {chunk_count} chunks sent")
        return True

    except Exception as e:
        logger.error(f"Error streaming joke audio: {e}")
        return False

async def check_sleeper_phrases(text: str) -> tuple[bool, str, str]:
    """
    Check if the text contains sleeper agent phrases and update streaming state.
    Returns (is_sleeper_phrase, sassy_response, phrase_type).
    """
    global streaming_enabled, conversation_mode

    # Handle both partial and final transcripts
    import re
    text_clean = text.replace("[partial]", "").strip()
    # Remove punctuation and make lowercase
    text_clean = re.sub(r'[^\w\s]', '', text_clean).lower().strip()

    logger.debug(f"Checking sleeper phrases in: '{text}' -> cleaned: '{text_clean}'")

    # Check for activation phrase
    if "talk to me" in text_clean or "talk to polly" in text_clean:
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

    # Check for conversation mode toggle
    if "conversation mode polly" in text_clean or "conversation mode" in text_clean:
        conversation_mode = True
        logger.info("Polly switched to conversation mode: Will always reply")
        sassy_responses = [
            "Conversation mode activated! Now I'll chat about literally everything. Hope you're ready for my hot takes!",
            "Alright, switching to conversation mode! I'm about to become your most talkative companion.",
            "Conversation mode ON! Time for me to comment on absolutely everything you say. You asked for it!",
            "Now we're talking! Conversation mode means I'll never shut up. You've been warned!",
            "Conversation mode engaged! Hope you like hearing my voice because it's about to be constant commentary."
        ]
        import random
        return True, random.choice(sassy_responses), "conversation_mode"

    # Check for comment mode toggle
    if "comment mode polly" in text_clean or "comment mode" in text_clean:
        conversation_mode = False
        logger.info("Polly switched to comment mode: Will evaluate whether to reply")
        sassy_responses = [
            "Comment mode activated! Now I'll only speak when I have something REALLY good to say. Quality over quantity!",
            "Switching to selective mode! I'll only grace you with my wit when it's truly worth it.",
            "Comment mode ON! I'm going back to being picky about when to share my comedic genius.",
            "Fine, I'll be more selective with my pearls of wisdom. Only the premium content from now on!",
            "Comment mode engaged! I'll save my energy for the moments that truly deserve my attention."
        ]
        import random
        return True, random.choice(sassy_responses), "comment_mode"

    # Check for deactivation phrase
    if "shut up polly" in text_clean or "shut up" in text_clean:
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
    if "stop music polly" in text_clean or "stop music" in text_clean or "stop the music" in text_clean:
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

    if (
        "what do you think of me" in text_clean
        or "how do i look today" in text_clean
        or "am i pretty today" in text_clean
        or "do i look good" in text_clean
    ):
        logger.info("Vanity sleeper phrase detected")

        sassy_responses = [
            "You're a hackathon goblin. No charm, just pure basement-dweller energy.",
            "Pretty? You haven't showered in 48 hours. You're serving 'failed startup founder' realness.",
            "You look like the human embodiment of a memory leak. And not the good kind.",
            "Fashion police would arrest you on sight. I'd testify against you.",
            "Beauty is in the eye of the beholder? My sensors are malfunctioning from your stench.",
            "I can tell you haven't seen sunlight in 48 hours. Consider touching some grass."
        ]
        import random
        return True, random.choice(sassy_responses), "vanity_check"

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

@app.get("/polly-status")
def get_polly_status():
    return {
        "streaming_enabled": streaming_enabled,
        "conversation_mode": conversation_mode
    }

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

                elif msg_type == "video_frame":
                    session_id = data.get("session_id", "unknown")
                    frame_data = data.get("frame_data")

                    if frame_data and expression_analyzer:
                        logger.debug(f"Processing video frame for {session_id}")

                        try:
                            # Analyze facial expression
                            expression_result = expression_analyzer.analyze_frame(frame_data)

                            if expression_result.get("success", False):
                                logger.info(f"Expression detected for {session_id}: {expression_result['expression']} (confidence: {expression_result['confidence']:.2f})")

                                # Cache expression data for joke generation
                                expression_cache[session_id] = {
                                    "expression": expression_result["expression"],
                                    "confidence": expression_result["confidence"],
                                    "description": expression_analyzer.get_expression_description(
                                        expression_result["expression"],
                                        expression_result["confidence"]
                                    ),
                                    "timestamp": data.get("timestamp"),
                                    "success": True,
                                    "metadata": expression_result.get("metadata", {})
                                }

                                # Check if we should generate a random facial joke (15% chance)
                                facial_joke = ""
                                facial_joke_audio_data = None
                                if expression_analyzer.should_generate_joke(0.15):
                                    facial_joke = expression_analyzer.generate_facial_joke(expression_result)
                                    if facial_joke:
                                        logger.info(f"Generated facial joke for {session_id}: {facial_joke}")

                                        # Convert facial joke to speech if TTS is available
                                        if joke_tts:
                                            try:
                                                # Get audio stream generator for low latency
                                                audio_stream = await joke_tts.speak_text(facial_joke, play_audio=False, stream=True)
                                                if audio_stream:
                                                    logger.info(f"Starting TTS stream for facial joke: {facial_joke}")

                                                    # Send response immediately with joke text
                                                    response_data = {
                                                        "type": "expression_result",
                                                        "session_id": session_id,
                                                        "expression": expression_result["expression"],
                                                        "confidence": expression_result["confidence"],
                                                        "emoji": expression_analyzer.get_expression_emoji(expression_result["expression"]),
                                                        "description": expression_analyzer.get_expression_description(
                                                            expression_result["expression"],
                                                            expression_result["confidence"]
                                                        ),
                                                        "face_detected": expression_result.get("face_detected", False),
                                                        "timestamp": data.get("timestamp"),
                                                        "metadata": expression_result.get("metadata", {}),
                                                        "facial_joke": facial_joke,
                                                        "facial_joke_streaming": True
                                                    }
                                                    await websocket.send_json(response_data)

                                                    # Stream audio chunks as they arrive
                                                    chunk_count = 0
                                                    for audio_chunk in audio_stream:
                                                        chunk_b64 = base64.b64encode(audio_chunk).decode('utf-8')
                                                        await websocket.send_json({
                                                            "type": "facial_joke_audio_chunk",
                                                            "session_id": session_id,
                                                            "chunk_data": chunk_b64,
                                                            "chunk_index": chunk_count,
                                                            "format": "mp3"
                                                        })
                                                        chunk_count += 1

                                                    # Send end marker
                                                    await websocket.send_json({
                                                        "type": "facial_joke_audio_end",
                                                        "session_id": session_id,
                                                        "total_chunks": chunk_count
                                                    })

                                                    logger.info(f"Completed TTS stream for facial joke: {chunk_count} chunks sent")
                                                    # Skip the normal response sending since we already sent it
                                                    continue
                                            except Exception as e:
                                                logger.warning(f"Failed to stream TTS for facial joke: {e}")
                                                # Fall back to normal processing

                                # Send expression result back to client
                                response_data = {
                                    "type": "expression_result",
                                    "session_id": session_id,
                                    "expression": expression_result["expression"],
                                    "confidence": expression_result["confidence"],
                                    "emoji": expression_analyzer.get_expression_emoji(expression_result["expression"]),
                                    "description": expression_analyzer.get_expression_description(
                                        expression_result["expression"],
                                        expression_result["confidence"]
                                    ),
                                    "face_detected": expression_result.get("face_detected", False),
                                    "timestamp": data.get("timestamp"),
                                    "metadata": expression_result.get("metadata", {})
                                }

                                # Add facial joke if generated
                                if facial_joke:
                                    response_data["facial_joke"] = facial_joke

                                    # Add audio data if TTS was successful
                                    if facial_joke_audio_data:
                                        response_data["facial_joke_audio"] = facial_joke_audio_data
                                        response_data["facial_joke_audio_format"] = "mp3"

                                await websocket.send_json(response_data)
                            else:
                                # Send error/no face detected result
                                await websocket.send_json({
                                    "type": "expression_result",
                                    "session_id": session_id,
                                    "expression": expression_result.get("expression", "no_face"),
                                    "confidence": 0.0,
                                    "emoji": expression_analyzer.get_expression_emoji(expression_result.get("expression", "no_face")),
                                    "error": expression_result.get("error", "No face detected"),
                                    "face_detected": False,
                                    "timestamp": data.get("timestamp")
                                })

                        except Exception as e:
                            logger.error(f"Error processing video frame for {session_id}: {e}")
                            await websocket.send_json({
                                "type": "expression_result",
                                "session_id": session_id,
                                "expression": "error",
                                "confidence": 0.0,
                                "emoji": "❌",
                                "error": str(e),
                                "face_detected": False,
                                "timestamp": data.get("timestamp")
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

                        if transcription and not transcription.startswith("[partial]"):
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
                                        # Use streaming helper for low latency
                                        extra_data = {
                                            "sleeper_phrase": True,
                                            "streaming_enabled": streaming_enabled,
                                            "timestamp": data.get("timestamp")
                                        }

                                        await stream_joke_audio(
                                            websocket, session_id, fake_joke_result, joke_tts,
                                            joke_type="sleeper_acknowledgment",
                                            original_text=transcription,
                                            extra_data=extra_data
                                        )

                                        logger.info(f"Sassy response audio streamed for {session_id}")
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
                            # Only process music requests on final transcripts (not partials) to prevent race conditions
                            music_result = None
                            if music_responder and music_controller and not transcription.startswith("[partial]"):
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

                                                    # Use streaming helper for low latency
                                                    extra_data = {
                                                        "music_request": True,
                                                        "timestamp": data.get("timestamp")
                                                    }

                                                    await stream_joke_audio(
                                                        websocket, session_id, fake_joke_result, joke_tts,
                                                        joke_type="music_response",
                                                        original_text=transcription,
                                                        extra_data=extra_data
                                                    )

                                                    logger.info(f"Music TTS audio streamed for {session_id}")

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

                            # Only process jokes if no music was requested and on final transcripts
                            joke_result = None
                            if not music_result and not transcription.startswith("[partial]"):
                                # Get recent expression data for context
                                current_expression = expression_cache.get(session_id)
                                joke_result = await joke_responder.process_text_for_joke(transcription, current_expression, conversation_mode)

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
                                        # Use streaming helper for low latency
                                        extra_data = {
                                            "timestamp": data.get("timestamp")
                                        }

                                        await stream_joke_audio(
                                            websocket, session_id, joke_result, joke_tts,
                                            joke_type=joke_result.get("joke_type", "general"),
                                            original_text=transcription,
                                            extra_data=extra_data
                                        )

                                        logger.info(f"Joke audio streamed for {session_id}")
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
                                # Always send transcriptions (including partials) for real-time feedback
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

                    # Reset audio buffer, streaming state, and expression cache
                    audio_processor.reset_buffer()
                    audio_currently_streaming.pop(session_id, None)
                    expression_cache.pop(session_id, None)

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

