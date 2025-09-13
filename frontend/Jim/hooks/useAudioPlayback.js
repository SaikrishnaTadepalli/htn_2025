import { useState, useEffect, useRef } from 'react';
import { Audio } from 'expo-av';
import * as FileSystem from 'expo-file-system';
import { AUDIO_CONFIG, AUDIO_STATES } from '../utils/audioConfig';
import AudioStreamingService from '../services/AudioStreamingService';

export const useAudioPlayback = () => {
  const [isPlaying, setIsPlaying] = useState(false);
  const [playbackState, setPlaybackState] = useState(AUDIO_STATES.IDLE);
  const [error, setError] = useState(null);
  const [volume, setVolume] = useState(1.0);
  const [bufferedChunks, setBufferedChunks] = useState(0);

  const soundRef = useRef(null);
  const audioQueueRef = useRef([]);
  const isProcessingRef = useRef(false);
  const playbackIntervalRef = useRef(null);

  useEffect(() => {
    initializeAudio();
    setupWebSocketListener();
    return cleanup;
  }, []);

  const initializeAudio = async () => {
    try {
      // Set audio mode for playback
      await Audio.setAudioModeAsync({
        allowsRecordingIOS: false,
        staysActiveInBackground: true,
        playsInSilentModeIOS: true,
        shouldDuckAndroid: true,
        playThroughEarpieceAndroid: false,
      });

      console.log('[useAudioPlayback] Audio initialized');
    } catch (err) {
      console.error('[useAudioPlayback] Failed to initialize audio:', err);
      setError(err);
      setPlaybackState(AUDIO_STATES.ERROR);
    }
  };

  const setupWebSocketListener = () => {
    // Listen for incoming audio chunks from WebSocket service
    AudioStreamingService.on('incoming_audio_chunk', handleIncomingAudioChunk);
  };

  const handleIncomingAudioChunk = (audioChunk) => {
    // Add incoming audio chunk to queue
    audioQueueRef.current.push(audioChunk);
    setBufferedChunks(audioQueueRef.current.length);

    console.log(`[useAudioPlayback] Added chunk ${audioChunk.index} to queue. Queue length: ${audioQueueRef.current.length}`);

    // Start processing if we have enough chunks buffered or already playing
    if (!isProcessingRef.current && (audioQueueRef.current.length >= AUDIO_CONFIG.playback.bufferSize || isPlaying)) {
      processAudioQueue();
    }
  };

  const processAudioQueue = async () => {
    if (isProcessingRef.current || audioQueueRef.current.length === 0) {
      return;
    }

    isProcessingRef.current = true;
    setPlaybackState(AUDIO_STATES.PLAYING);

    try {
      while (audioQueueRef.current.length > 0) {
        const audioChunk = audioQueueRef.current.shift();
        setBufferedChunks(audioQueueRef.current.length);

        await playAudioChunk(audioChunk);

        // Small delay between chunks to allow for smooth playback
        await new Promise(resolve => setTimeout(resolve, 10));
      }
    } catch (err) {
      console.error('[useAudioPlayback] Error processing audio queue:', err);
      setError(err);
      setPlaybackState(AUDIO_STATES.ERROR);
    } finally {
      isProcessingRef.current = false;
      setPlaybackState(AUDIO_STATES.IDLE);
      setIsPlaying(false);
    }
  };

  const playAudioChunk = async (audioChunk) => {
    try {
      // Convert base64 to file and play
      const tempUri = `${FileSystem.documentDirectory}temp_audio_${audioChunk.index}.m4a`;

      // Write base64 data to temporary file
      await FileSystem.writeAsStringAsync(tempUri, audioChunk.data, {
        encoding: FileSystem.EncodingType.Base64,
      });

      // Create and play sound
      const { sound } = await Audio.Sound.createAsync(
        { uri: tempUri },
        { shouldPlay: true, volume: volume }
      );

      soundRef.current = sound;
      setIsPlaying(true);

      // Wait for playback to finish
      await new Promise((resolve) => {
        sound.setOnPlaybackStatusUpdate((status) => {
          if (status.didJustFinish) {
            resolve();
          }
        });
      });

      // Cleanup
      await sound.unloadAsync();
      await FileSystem.deleteAsync(tempUri, { idempotent: true });

      console.log(`[useAudioPlayback] Played chunk ${audioChunk.index}`);
    } catch (err) {
      console.error('[useAudioPlayback] Failed to play audio chunk:', err);
      setError(err);
    }
  };

  const startPlayback = async () => {
    try {
      setError(null);

      // Simulate receiving audio chunks by triggering the WebSocket service
      AudioStreamingService.simulateIncomingAudioChunks();

      console.log('[useAudioPlayback] Playback started (simulation)');
    } catch (err) {
      console.error('[useAudioPlayback] Failed to start playback:', err);
      setError(err);
      setPlaybackState(AUDIO_STATES.ERROR);
    }
  };

  const stopPlayback = async () => {
    try {
      // Stop current sound if playing
      if (soundRef.current) {
        await soundRef.current.stopAsync();
        await soundRef.current.unloadAsync();
        soundRef.current = null;
      }

      // Clear the audio queue
      audioQueueRef.current = [];
      isProcessingRef.current = false;
      setBufferedChunks(0);

      setIsPlaying(false);
      setPlaybackState(AUDIO_STATES.IDLE);

      console.log('[useAudioPlayback] Playback stopped');
    } catch (err) {
      console.error('[useAudioPlayback] Failed to stop playback:', err);
      setError(err);
    }
  };

  const pausePlayback = async () => {
    try {
      if (soundRef.current) {
        await soundRef.current.pauseAsync();
      }

      isProcessingRef.current = false;
      setIsPlaying(false);
      setPlaybackState(AUDIO_STATES.IDLE);

      console.log('[useAudioPlayback] Playback paused');
    } catch (err) {
      console.error('[useAudioPlayback] Failed to pause playback:', err);
      setError(err);
    }
  };

  const resumePlayback = async () => {
    try {
      if (soundRef.current) {
        await soundRef.current.playAsync();
        setIsPlaying(true);
        setPlaybackState(AUDIO_STATES.PLAYING);
      } else if (audioQueueRef.current.length > 0) {
        // Resume processing queue
        processAudioQueue();
      }

      console.log('[useAudioPlayback] Playback resumed');
    } catch (err) {
      console.error('[useAudioPlayback] Failed to resume playback:', err);
      setError(err);
    }
  };

  const adjustVolume = async (newVolume) => {
    if (newVolume < 0 || newVolume > 1) {
      return;
    }

    try {
      setVolume(newVolume);

      if (soundRef.current) {
        await soundRef.current.setVolumeAsync(newVolume);
      }

      console.log(`[useAudioPlayback] Volume set to ${newVolume}`);
    } catch (err) {
      console.error('[useAudioPlayback] Failed to adjust volume:', err);
      setError(err);
    }
  };

  const cleanup = () => {
    // Remove WebSocket listener
    AudioStreamingService.off('incoming_audio_chunk', handleIncomingAudioChunk);

    // Stop playback and clear queue
    if (soundRef.current) {
      soundRef.current.stopAsync().catch(console.error);
      soundRef.current.unloadAsync().catch(console.error);
    }

    audioQueueRef.current = [];
    isProcessingRef.current = false;

    if (playbackIntervalRef.current) {
      clearInterval(playbackIntervalRef.current);
    }
  };

  return {
    isPlaying,
    playbackState,
    error,
    volume,
    bufferedChunks,
    queueLength: audioQueueRef.current.length,
    startPlayback,
    stopPlayback,
    pausePlayback,
    resumePlayback,
    adjustVolume,
  };
};