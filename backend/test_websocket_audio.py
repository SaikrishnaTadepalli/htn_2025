#!/usr/bin/env python3
"""
Test WebSocket audio streaming - simulates frontend sending audio chunks
"""

import asyncio
import logging
import websockets
import pyaudio
import json
import base64

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WebSocketAudioTester:
    def __init__(self, websocket_url="ws://localhost:8000/ws/audio"):
        self.websocket_url = websocket_url
        self.audio = pyaudio.PyAudio()

        # Audio settings
        self.chunk_size = 1024
        self.sample_rate = 16000
        self.channels = 1
        self.format = pyaudio.paInt16

    async def test_audio_streaming(self, duration_seconds=10):
        """Test streaming audio via WebSocket"""
        print(f"Connecting to {self.websocket_url}")
        print(f"Will stream audio for {duration_seconds} seconds")
        print("Speak into your microphone!")

        try:
            async with websockets.connect(self.websocket_url) as websocket:
                print("Connected! Starting audio stream...")

                # Open microphone
                stream = self.audio.open(
                    format=self.format,
                    channels=self.channels,
                    rate=self.sample_rate,
                    input=True,
                    frames_per_buffer=self.chunk_size
                )

                start_time = asyncio.get_event_loop().time()

                # Send session start message
                await websocket.send(json.dumps({
                    "type": "session_start",
                    "session_id": "test_session_123"
                }))

                while (asyncio.get_event_loop().time() - start_time) < duration_seconds:
                    # Read audio chunk
                    audio_data = stream.read(self.chunk_size, exception_on_overflow=False)

                    # Encode audio data
                    audio_b64 = base64.b64encode(audio_data).decode('utf-8')

                    # Send audio chunk
                    message = {
                        "type": "audio_chunk",
                        "session_id": "test_session_123",
                        "audio_data": audio_b64,
                        "timestamp": asyncio.get_event_loop().time()
                    }

                    await websocket.send(json.dumps(message))

                    # Listen for responses
                    try:
                        response = await asyncio.wait_for(websocket.recv(), timeout=0.01)
                        data = json.loads(response)
                        print(f"Received: {data}")
                    except asyncio.TimeoutError:
                        pass  # No response yet

                    await asyncio.sleep(0.1)

                # Send session end
                await websocket.send(json.dumps({
                    "type": "session_end",
                    "session_id": "test_session_123"
                }))

                stream.stop_stream()
                stream.close()
                print("Audio streaming test completed!")

        except Exception as e:
            logger.error(f"WebSocket test failed: {e}")

    def cleanup(self):
        """Clean up audio resources"""
        self.audio.terminate()

async def main():
    tester = WebSocketAudioTester()

    try:
        print("WebSocket Audio Streaming Test")
        print("=" * 40)
        print("Make sure your WebSocket server is running on localhost:8000")

        duration = input("Enter test duration in seconds (default 10): ")
        try:
            duration = int(duration) if duration else 10
        except ValueError:
            duration = 10

        await tester.test_audio_streaming(duration)

    except KeyboardInterrupt:
        print("\nTest interrupted by user")
    except Exception as e:
        logger.error(f"Test failed: {e}")
    finally:
        tester.cleanup()

if __name__ == "__main__":
    asyncio.run(main())