export const AUDIO_CONFIG = {
  recording: {
    android: {
      extension: '.m4a',
      outputFormat: 'mpeg4',
      audioEncoder: 'aac',
      sampleRate: 16000,
      numberOfChannels: 1,
      bitRate: 64000,
    },
    ios: {
      extension: '.m4a',
      outputFormat: 'mpeg4',
      audioEncoder: 'aac',
      sampleRate: 16000,
      numberOfChannels: 1,
      bitRate: 64000,
      linearPCMBitDepth: 16,
      linearPCMIsBigEndian: false,
      linearPCMIsFloat: false,
    },
    web: {
      extension: '.m4a',
      outputFormat: 'mpeg4',
      audioEncoder: 'aac',
      sampleRate: 16000,
      numberOfChannels: 1,
      bitRate: 64000,
    }
  },

  chunking: {
    chunkDurationMs: 500, // 0.5 second chunks
    maxChunksInMemory: 20, // Keep max 10 seconds worth of chunks
    overlapMs: 50, // Small overlap to prevent audio gaps
  },

  playback: {
    bufferSize: 5, // Number of chunks to buffer before playing
    maxBufferSize: 20, // Maximum chunks in playback buffer
  },

  websocket: {
    maxReconnectAttempts: 5,
    reconnectInterval: 1000,
    pingInterval: 30000,
    chunkTimeout: 5000, // Timeout for chunk transmission
  },
};

export const WEBSOCKET_EVENTS = {
  AUDIO_DATA: 'audio_data',
  START_RECORDING: 'start_recording',
  STOP_RECORDING: 'stop_recording',
  START_PLAYBACK: 'start_playback',
  STOP_PLAYBACK: 'stop_playback',
  CONNECTION_STATUS: 'connection_status',
  ERROR: 'error',
};

export const AUDIO_STATES = {
  IDLE: 'idle',
  RECORDING: 'recording',
  PLAYING: 'playing',
  CONNECTING: 'connecting',
  CONNECTED: 'connected',
  DISCONNECTED: 'disconnected',
  ERROR: 'error',
};