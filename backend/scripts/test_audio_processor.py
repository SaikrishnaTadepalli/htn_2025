#!/usr/bin/env python3

import asyncio
import logging
import sys
import websockets
import json
import base64
import pyaudio
import io
from pydub import AudioSegment
from pydub.playback import play

import time

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class MicrophoneStreamer:
    def __init__(self, websocket_url="ws://localhost:8000/ws/audio"):
        self.websocket_url = websocket_url
        self.websocket = None
        self.session_id = f"test_session_{int(time.time())}"
        
        self.sample_rate = 16000
        self.channels = 1
        self.chunk_duration = 0.5  # 0.5 seconds
        self.chunk_size = int(self.sample_rate * self.chunk_duration)  # 8000 samples
        
        self.audio = pyaudio.PyAudio()
        self.format = pyaudio.paInt16
        self.stream = None
        self.is_streaming = False

    async def connect_websocket(self):
        try:
            self.websocket = await websockets.connect(
                self.websocket_url,
                ping_interval=20,  # Send ping every 20 seconds
                ping_timeout=10,   # Wait 10 seconds for pong
                close_timeout=10   # Wait 10 seconds for close
            )
            logger.info(f"Connected to WebSocket: {self.websocket_url}")
            
            session_start_msg = {
                "type": "session_start",
                "session_id": self.session_id
            }
            await self.websocket.send(json.dumps(session_start_msg))
            logger.info(f"Sent session start: {session_start_msg}")
            
        except Exception as e:
            logger.error(f"Failed to connect to WebSocket: {e}")
            raise

    async def listen_for_responses(self):
        try:
            while self.is_streaming:
                try:
                    response = await asyncio.wait_for(self.websocket.recv(), timeout=1.0)
                    data = json.loads(response)
                    if data.get("type") == "transcription":
                        streaming_disabled = data.get("streaming_disabled", False)
                        audio_busy = data.get("audio_busy", False)
                        status = ""
                        if streaming_disabled:
                            status = " (STREAMING DISABLED)"
                        elif audio_busy:
                            status = " (AUDIO BUSY)"
                        print(f"Transcribed: '{data.get('text')}'{status}")

                    elif data.get("type") == "sleeper_phrase":
                        phrase_type = data.get("phrase_type", "unknown")
                        sassy_response = data.get("sassy_response", "")
                        streaming_enabled = data.get("streaming_enabled", True)

                        if phrase_type == "activate":
                            print(f"🟢 SLEEPER ACTIVATED: {sassy_response}")
                        elif phrase_type == "deactivate":
                            print(f"🔴 SLEEPER DEACTIVATED: {sassy_response}")
                        elif phrase_type == "stop_music":
                            print(f"⏹️  MUSIC STOPPED: {sassy_response}")

                        print(f"    Streaming enabled: {streaming_enabled}")

                    elif data.get("type") == "music_response":
                        music_request = data.get("music_request", {})
                        music_result = data.get("music_result", {})

                        artist = music_request.get("artist", "Unknown")
                        song = music_request.get("song", "Unknown")

                        print(f"🎵 MUSIC REQUEST: {artist} - {song}")

                        if music_result.get("success"):
                            search_result = music_result.get("search_result", {})
                            track_name = search_result.get("track_name", "Unknown")
                            artist_name = search_result.get("artist_name", "Unknown")
                            print(f"✅ Now playing: {track_name} by {artist_name}")
                        else:
                            error = music_result.get("error", "Unknown error")
                            action = music_result.get("action", "unknown")
                            print(f"❌ Music failed ({action}): {error}")

                    elif data.get("type") == "joke_response":
                        print(f"🎭 JOKE: {data.get('joke')}")
                        print(f"    Original: '{data.get('original_text')}'")
                        print(f"    Type: {data.get('joke_type')}, Confidence: {data.get('confidence'):.2f}")

                    elif data.get("type") == "joke_audio":
                        sleeper_phrase = data.get("sleeper_phrase", False)
                        music_request = data.get("music_request", False)

                        if sleeper_phrase:
                            print(f"🔊 Playing sleeper response audio...")
                        elif music_request:
                            print(f"🎵🔊 Playing music announcement audio...")
                        else:
                            print(f"🔊 Playing joke audio...")

                        try:
                            # Decode the base64 audio data
                            audio_b64 = data.get('audio_data')
                            if audio_b64:
                                audio_bytes = base64.b64decode(audio_b64)

                                # Create AudioSegment from bytes and play
                                audio = AudioSegment.from_file(io.BytesIO(audio_bytes), format="mp3")
                                play(audio)
                                if music_request:
                                    print(f"✅ Music announcement played: '{data.get('joke_text')}' (Music should start playing now)")
                                else:
                                    print(f"✅ Audio played for: '{data.get('joke_text')}'")
                            else:
                                print("❌ No audio data received")
                        except Exception as e:
                            print(f"❌ Error playing audio: {e}")

                    elif data.get("type") == "session_started":
                        print(f"✅ Session started: {data.get('session_id')}")

                    elif data.get("type") == "session_ended":
                        print(f"🔚 Session ended: {data.get('session_id')}")

                    else:
                        print(f"📨 Unknown message type: {data.get('type')}")
                        print(f"    Data: {data}")
                except asyncio.TimeoutError:
                    continue
                except Exception as e:
                    logger.error(f"Error receiving response: {e}")
                    break
        except asyncio.CancelledError:
            logger.info("Response listening cancelled")

    async def stream_audio(self, duration_seconds=float('inf')):
        if duration_seconds == float('inf'):
            print("Starting infinite audio streaming...")
        else:
            print(f"Starting {duration_seconds}-second audio streaming...")
        print("Speak into your microphone!")
        print(f"Streaming to: {self.websocket_url}")

        try:
            await self.connect_websocket()
            
            self.stream = self.audio.open(
                format=self.format,
                channels=self.channels,
                rate=self.sample_rate,
                input=True,
                frames_per_buffer=self.chunk_size
            )

            self.is_streaming = True
            start_time = time.time()

            response_task = asyncio.create_task(self.listen_for_responses())
            
            while self.is_streaming and (duration_seconds == float('inf') or (time.time() - start_time) < duration_seconds):
                try:
                    audio_data = self.stream.read(self.chunk_size, exception_on_overflow=False)
                    
                    # Debug: Check audio levels
                    import struct
                    audio_samples = struct.unpack(f'{self.chunk_size}h', audio_data)
                    max_amplitude = max(abs(sample) for sample in audio_samples)
                    avg_amplitude = sum(abs(sample) for sample in audio_samples) / len(audio_samples)
                    
                    audio_b64 = base64.b64encode(audio_data).decode('utf-8')
                    
                    message = {
                        "type": "audio_chunk",
                        "session_id": self.session_id,
                        "audio_data": audio_b64,
                        "timestamp": time.time()
                    }
                    
                    await self.websocket.send(json.dumps(message))
                    logger.info(f"Sent audio chunk: {len(audio_data)} bytes | Max: {max_amplitude} | Avg: {avg_amplitude:.1f}")
                    
                    await asyncio.sleep(0.1)
                    
                except websockets.exceptions.ConnectionClosed as e:
                    logger.error(f"WebSocket connection closed: {e}")
                    break
                except Exception as e:
                    logger.error(f"Error in streaming loop: {e}")
                    break
            
            response_task.cancel()

        except Exception as e:
            logger.error(f"Error during audio streaming: {e}")
        finally:
            await self.cleanup()

    async def cleanup(self):
        self.is_streaming = False
        
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
            
        if self.websocket:
            try:
                await self.websocket.send(json.dumps({
                    "type": "session_end",
                    "session_id": self.session_id
                }))
                await self.websocket.close()
            except:
                pass
                
        self.audio.terminate()
        logger.info("Cleanup completed")

async def main():
    streamer = MicrophoneStreamer()

    try:
        print("Infinite Microphone Audio Streamer with Spotify Support")
        print("=" * 55)
        print("Streaming microphone audio to WebSocket server...")
        print("Make sure the server is running on localhost:8000")
        print()
        print("Voice Commands to Test:")
        print("  🎭 Jokes: Say something funny to trigger joke responses")
        print("  🟢 Activate: 'Talk to me Jim' - Enable streaming")
        print("  🔴 Deactivate: 'Shut up Jim' - Disable streaming")
        print("  🎵 Music: 'Play [artist/song]' - Start Spotify playback")
        print("  ⏹️  Stop Music: 'Stop music Jim' - Stop Spotify playback")
        print()
        print("Press Ctrl+C to stop")
        print()

        await streamer.stream_audio(float('inf'))

    except KeyboardInterrupt:
        print("\nStreaming stopped by user")
    except Exception as e:
        logger.error(f"Streaming failed: {e}")
    finally:
        await streamer.cleanup()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"Failed to run test: {e}")
        sys.exit(1)