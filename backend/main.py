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
                    logger.info(f"Received audio chunk for {session_id}: {len(audio_b64)} bytes")

                    if audio_b64:
                        # Decode audio data
                        audio_data = base64.b64decode(audio_b64)
                        logger.debug(f"Processing audio chunk for {session_id}: {len(audio_data)} bytes")

                        # Process with AudioProcessor
                        transcription = await audio_processor.process_audio_chunk(
                            audio_data, session_id
                        )

                        if transcription:
                            logger.info(f"Transcription for {session_id}: {transcription}")

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

@app.websocket("/ws/text")
async def websocket_text_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for text messages that can trigger joke responses.
    """
    session_id = None

    try:
        # Accept connection
        await websocket.accept()
        logger.info("Text WebSocket connection established")

        async for message in websocket:
            try:
                data = json.loads(message)
                msg_type = data.get("type")

                if msg_type == "session_start":
                    session_id = data.get("session_id", f"text_session_{id(websocket)}")
                    await manager.connect(websocket, session_id)

                    logger.info(f"Text session started: {session_id}")
                    await websocket.send_json({
                        "type": "session_started",
                        "session_id": session_id,
                        "status": "ready"
                    })

                elif msg_type == "text_message":
                    session_id = data.get("session_id", "unknown")
                    text_content = data.get("text", "")

                    if text_content:
                        logger.info(f"Text message for {session_id}: {text_content}")

                        # Send the text message back
                        await websocket.send_json({
                            "type": "text_received",
                            "session_id": session_id,
                            "text": text_content,
                            "timestamp": data.get("timestamp")
                        })

                        # Check if we should respond with a joke
                        try:
                            joke_response_data = await joke_responder.handle_websocket_message({
                                "type": "text_message",
                                "text": text_content,
                                "session_id": session_id
                            })
                            
                            if joke_response_data:
                                logger.info(f"Generated joke response for {session_id}: {joke_response_data['joke_response']}")
                                
                                # Send joke response back to client
                                await websocket.send_json({
                                    "type": "joke_response",
                                    "session_id": session_id,
                                    "original_text": joke_response_data["original_text"],
                                    "joke_response": joke_response_data["joke_response"],
                                    "joke_type": joke_response_data["joke_type"],
                                    "confidence": joke_response_data["confidence"],
                                    "timestamp": data.get("timestamp")
                                })
                                
                                # Convert joke to speech if TTS is available
                                if joke_tts:
                                    try:
                                        logger.info(f"Converting joke to speech for {session_id}")
                                        audio_data = await joke_tts.speak_joke(joke_response_data, play_audio=False)
                                        
                                        if audio_data:
                                            # Send audio data back to client (base64 encoded)
                                            audio_b64 = base64.b64encode(audio_data).decode('utf-8')
                                            await websocket.send_json({
                                                "type": "joke_audio",
                                                "session_id": session_id,
                                                "audio_data": audio_b64,
                                                "joke_text": joke_response_data["joke_response"],
                                                "timestamp": data.get("timestamp")
                                            })
                                            logger.info(f"Joke audio sent for {session_id}")
                                        else:
                                            logger.warning(f"Failed to generate audio for joke in {session_id}")
                                    except Exception as e:
                                        logger.error(f"Error generating joke audio for {session_id}: {e}")
                                
                        except Exception as e:
                            logger.error(f"Error processing joke response for {session_id}: {e}")

                elif msg_type == "session_end":
                    session_id = data.get("session_id", "unknown")
                    logger.info(f"Text session ended: {session_id}")

                    await websocket.send_json({
                        "type": "session_ended",
                        "session_id": session_id
                    })

            except json.JSONDecodeError:
                logger.error("Invalid JSON received in text WebSocket")
            except Exception as e:
                logger.error(f"Error processing text message: {e}")

    except WebSocketDisconnect:
        logger.info(f"Text WebSocket disconnected for session: {session_id}")
        if session_id:
            manager.disconnect(websocket, session_id)
    except Exception as e:
        logger.error(f"Text WebSocket error: {e}")
