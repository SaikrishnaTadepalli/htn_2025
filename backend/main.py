from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import logging
import json
import base64
from audio_processor import AudioProcessor
from websocket_manager import manager
from joke_responder import JokeResponder

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI()

# Initialize audio processor and joke responder
audio_processor = AudioProcessor()
joke_responder = JokeResponder()

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
