import asyncio
import io
import logging
import numpy as np
from typing import Optional, Callable
import speech_recognition as sr
from pydub import AudioSegment

logger = logging.getLogger(__name__)

class AudioProcessor:
    def __init__(self):
        self.recognizer = sr.Recognizer()
        self.audio_buffer = bytearray()
        self.sample_rate = 16000
        self.chunk_duration_ms = 1000  # 1 second chunks
        self.silence_threshold = 500  # ms of silence before processing
        self.last_audio_time = 0

    async def process_audio_chunk(self, audio_data: bytes, session_id: str) -> Optional[str]:
        """
        Process incoming audio chunk and return transcription if speech detected
        """
        try:
            # Add to buffer
            self.audio_buffer.extend(audio_data)

            # Check if we have enough data to process
            if len(self.audio_buffer) >= self.chunk_duration_ms * self.sample_rate * 2 // 1000:
                transcription = await self._transcribe_buffer(session_id)
                if transcription:
                    logger.info(f"Transcribed: {transcription}")
                    return transcription

        except Exception as e:
            logger.error(f"Error processing audio chunk: {e}")

        return None

    async def _transcribe_buffer(self, session_id: str) -> Optional[str]:
        """
        Transcribe the current audio buffer
        """
        try:
            if len(self.audio_buffer) == 0:
                return None

            # Convert buffer to audio format
            audio_segment = AudioSegment(
                data=bytes(self.audio_buffer),
                sample_width=2,  # 16-bit
                frame_rate=self.sample_rate,
                channels=1
            )

            # Clear buffer after taking snapshot
            buffer_copy = bytes(self.audio_buffer)
            self.audio_buffer.clear()

            # Convert to wav format for speech recognition
            wav_io = io.BytesIO()
            audio_segment.export(wav_io, format="wav")
            wav_io.seek(0)

            # Use speech recognition
            with sr.AudioFile(wav_io) as source:
                audio = self.recognizer.record(source)

            # Perform transcription
            try:
                text = self.recognizer.recognize_google(audio)
                return text.strip() if text else None
            except sr.UnknownValueError:
                logger.debug("Could not understand audio")
                return None
            except sr.RequestError as e:
                logger.error(f"Speech recognition error: {e}")
                return None

        except Exception as e:
            logger.error(f"Error in transcription: {e}")
            return None

    def reset_buffer(self):
        """Reset the audio buffer"""
        self.audio_buffer.clear()

    async def detect_silence(self, audio_data: bytes) -> bool:
        """
        Detect if audio chunk contains mostly silence
        """
        try:
            # Convert to numpy array for analysis
            audio_array = np.frombuffer(audio_data, dtype=np.int16)

            # Calculate RMS (root mean square) to detect volume
            rms = np.sqrt(np.mean(audio_array**2))

            # Threshold for silence detection (adjust as needed)
            silence_threshold = 1000

            return rms < silence_threshold

        except Exception as e:
            logger.error(f"Error detecting silence: {e}")
            return False