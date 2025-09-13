import { useState, useEffect, useRef } from 'react';
import { Audio } from 'expo-av';
import { Platform } from 'react-native';
import * as FileSystem from 'expo-file-system';
import { AUDIO_CONFIG, AUDIO_STATES } from '../utils/audioConfig';
import AudioStreamingService from '../services/AudioStreamingService';

export const useAudioRecording = () => {
  const [isRecording, setIsRecording] = useState(false);
  const [recordingState, setRecordingState] = useState(AUDIO_STATES.IDLE);
  const [error, setError] = useState(null);
  const [duration, setDuration] = useState(0);
  const [chunksRecorded, setChunksRecorded] = useState(0);

  const recordingRef = useRef(null);
  const chunkIntervalRef = useRef(null);
  const durationIntervalRef = useRef(null);
  const startTimeRef = useRef(null);
  const chunkCountRef = useRef(0);

  useEffect(() => {
    return cleanup;
  }, []);

  const getRecordingOptions = () => {
    const platform = Platform.OS;
    return AUDIO_CONFIG.recording[platform] || AUDIO_CONFIG.recording.android;
  };

  const startRecording = async () => {
    if (isRecording) {
      return;
    }

    try {
      setError(null);
      setRecordingState(AUDIO_STATES.RECORDING);

      // Set audio mode for recording
      await Audio.setAudioModeAsync({
        allowsRecordingIOS: true,
        playsInSilentModeIOS: true,
      });

      setIsRecording(true);
      startTimeRef.current = Date.now();
      chunkCountRef.current = 0;
      setChunksRecorded(0);

      // Start duration timer
      durationIntervalRef.current = setInterval(() => {
        if (startTimeRef.current) {
          setDuration(Math.floor((Date.now() - startTimeRef.current) / 1000));
        }
      }, 1000);

      // Start chunked recording
      startChunkedRecording();

      console.log('[useAudioRecording] Chunked recording started');
    } catch (err) {
      console.error('[useAudioRecording] Failed to start recording:', err);
      setError(err);
      setRecordingState(AUDIO_STATES.ERROR);
      setIsRecording(false);
    }
  };

  const startChunkedRecording = () => {
    recordNextChunk();
  };

  const recordNextChunk = async () => {
    if (!isRecording) return;

    try {
      // Create new recording instance for this chunk
      const recording = new Audio.Recording();
      recordingRef.current = recording;

      const options = getRecordingOptions();
      await recording.prepareToRecordAsync(Audio.RECORDING_OPTIONS_PRESET_HIGH_QUALITY);
      await recording.startAsync();

      // Record for the specified chunk duration
      setTimeout(async () => {
        if (recording && isRecording) {
          await stopCurrentChunk(recording);

          // Schedule next chunk if still recording
          if (isRecording) {
            setTimeout(() => recordNextChunk(), AUDIO_CONFIG.chunking.overlapMs);
          }
        }
      }, AUDIO_CONFIG.chunking.chunkDurationMs);

    } catch (err) {
      console.error('[useAudioRecording] Error in chunk recording:', err);
      setError(err);
    }
  };

  const stopCurrentChunk = async (recording) => {
    try {
      await recording.stopAndUnloadAsync();
      const uri = recording.getURI();

      if (uri) {
        chunkCountRef.current++;
        setChunksRecorded(chunkCountRef.current);

        // Read the chunk as base64 and send to WebSocket
        await processAudioChunk(uri, chunkCountRef.current);

        // Clean up the temporary file
        await FileSystem.deleteAsync(uri, { idempotent: true });
      }
    } catch (err) {
      console.error('[useAudioRecording] Error stopping chunk:', err);
    }
  };

  const processAudioChunk = async (uri, chunkIndex) => {
    try {
      // Read the audio file as base64
      const base64Audio = await FileSystem.readAsStringAsync(uri, {
        encoding: FileSystem.EncodingType.Base64,
      });

      // Create chunk metadata
      const audioChunk = {
        data: base64Audio,
        index: chunkIndex,
        timestamp: Date.now(),
        duration: AUDIO_CONFIG.chunking.chunkDurationMs,
        format: 'm4a',
      };

      // Send to WebSocket service
      AudioStreamingService.sendAudioChunk(audioChunk);

      console.log(`[useAudioRecording] Processed chunk ${chunkIndex}: ${base64Audio.length} chars`);
    } catch (err) {
      console.error('[useAudioRecording] Error processing chunk:', err);
    }
  };

  const stopRecording = async () => {
    if (!isRecording) {
      return;
    }

    try {
      setIsRecording(false);
      setRecordingState(AUDIO_STATES.IDLE);

      // Stop current recording if active
      if (recordingRef.current) {
        try {
          await recordingRef.current.stopAndUnloadAsync();
        } catch (err) {
          console.warn('[useAudioRecording] Error stopping final chunk:', err);
        }
        recordingRef.current = null;
      }

      // Clear timers
      if (durationIntervalRef.current) {
        clearInterval(durationIntervalRef.current);
        durationIntervalRef.current = null;
      }

      if (chunkIntervalRef.current) {
        clearInterval(chunkIntervalRef.current);
        chunkIntervalRef.current = null;
      }

      startTimeRef.current = null;
      setDuration(0);

      console.log(`[useAudioRecording] Recording stopped. Total chunks: ${chunkCountRef.current}`);
    } catch (err) {
      console.error('[useAudioRecording] Failed to stop recording:', err);
      setError(err);
      setRecordingState(AUDIO_STATES.ERROR);
    }
  };

  const pauseRecording = async () => {
    if (!isRecording) {
      return;
    }

    try {
      setIsRecording(false);
      setRecordingState(AUDIO_STATES.IDLE);

      // Stop current chunk
      if (recordingRef.current) {
        await recordingRef.current.stopAndUnloadAsync();
        recordingRef.current = null;
      }

      // Pause duration timer
      if (durationIntervalRef.current) {
        clearInterval(durationIntervalRef.current);
        durationIntervalRef.current = null;
      }

      console.log('[useAudioRecording] Recording paused');
    } catch (err) {
      console.error('[useAudioRecording] Failed to pause recording:', err);
      setError(err);
    }
  };

  const resumeRecording = async () => {
    if (isRecording) {
      return;
    }

    try {
      setIsRecording(true);
      setRecordingState(AUDIO_STATES.RECORDING);

      // Resume duration timer
      const pausedDuration = duration;
      startTimeRef.current = Date.now() - (pausedDuration * 1000);

      durationIntervalRef.current = setInterval(() => {
        if (startTimeRef.current) {
          setDuration(Math.floor((Date.now() - startTimeRef.current) / 1000));
        }
      }, 1000);

      // Resume chunked recording
      recordNextChunk();

      console.log('[useAudioRecording] Recording resumed');
    } catch (err) {
      console.error('[useAudioRecording] Failed to resume recording:', err);
      setError(err);
    }
  };

  const cleanup = () => {
    if (durationIntervalRef.current) {
      clearInterval(durationIntervalRef.current);
    }

    if (chunkIntervalRef.current) {
      clearInterval(chunkIntervalRef.current);
    }

    if (recordingRef.current && isRecording) {
      recordingRef.current.stopAndUnloadAsync().catch(console.error);
    }
  };

  const formatDuration = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  return {
    isRecording,
    recordingState,
    error,
    duration,
    chunksRecorded,
    formattedDuration: formatDuration(duration),
    startRecording,
    stopRecording,
    pauseRecording,
    resumeRecording,
  };
};