import { WEBSOCKET_EVENTS, AUDIO_STATES, AUDIO_CONFIG } from '../utils/audioConfig';

class AudioStreamingService {
  constructor() {
    this.listeners = new Map();
    this.connectionState = AUDIO_STATES.CONNECTED; // Simulated as always connected
    this.chunkBuffer = [];
    this.simulationInterval = null;
  }

  on(event, callback) {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, []);
    }
    this.listeners.get(event).push(callback);
  }

  off(event, callback) {
    if (this.listeners.has(event)) {
      const callbacks = this.listeners.get(event);
      const index = callbacks.indexOf(callback);
      if (index > -1) {
        callbacks.splice(index, 1);
      }
    }
  }

  emit(event, data) {
    if (this.listeners.has(event)) {
      this.listeners.get(event).forEach(callback => callback(data));
    }
  }

  // Chunk-based WebSocket methods
  sendAudioChunk(audioChunk) {
    console.log(`[WebSocket] Sending audio chunk ${audioChunk.index}: ${audioChunk.data.length} chars`);

    // Store in buffer for potential echo/testing
    this.chunkBuffer.push(audioChunk);

    // Keep buffer size manageable
    if (this.chunkBuffer.length > AUDIO_CONFIG.chunking.maxChunksInMemory) {
      this.chunkBuffer.shift();
    }

    // TODO: Implement actual WebSocket transmission
    // Example: this.ws.send(JSON.stringify({ type: 'audio_chunk', data: audioChunk }));
  }

  simulateIncomingAudioChunks() {
    let chunkIndex = 0;

    // Clear any existing simulation
    if (this.simulationInterval) {
      clearInterval(this.simulationInterval);
    }

    console.log('[WebSocket] Starting audio chunk simulation');

    // Simulate receiving chunks every 0.5 seconds
    this.simulationInterval = setInterval(() => {
      // Create mock audio chunk (base64 encoded silence or test tone)
      const mockBase64Audio = this.generateMockAudioChunk(chunkIndex);

      const mockChunk = {
        data: mockBase64Audio,
        index: chunkIndex++,
        timestamp: Date.now(),
        duration: AUDIO_CONFIG.chunking.chunkDurationMs,
        format: 'm4a',
      };

      console.log(`[WebSocket] Simulating incoming chunk ${mockChunk.index}`);
      this.emit('incoming_audio_chunk', mockChunk);

      // Stop after 10 chunks (5 seconds of simulation)
      if (chunkIndex >= 10) {
        clearInterval(this.simulationInterval);
        this.simulationInterval = null;
        console.log('[WebSocket] Audio chunk simulation complete');
      }
    }, AUDIO_CONFIG.chunking.chunkDurationMs);
  }

  generateMockAudioChunk(index) {
    // Generate a small mock audio file in base64
    // This is a minimal M4A header + silence - in real implementation this would be actual audio
    const mockM4AHeader = 'AAAAGGZ0eXBpc29tAAABzGlzb21pc28yYXZjMW1wNDEAAAAAAAAAAAT4bW9vdgAAAGxtdmhkAAAAAAAAAAAAAAAAAAAAATAAAANQAAEAAAEAAAAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAADAAAB2HRyYWsAAABcdGtoZAAAAAAAAAAAAAAAAAABAAAAAAAAA1AAAAAAAAAAAAAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABAAABwG1kaWEAAAAgbWRoZAAAAAAAAAAAAAAAAAAoBAAAAKAVeQAAAAAALWhkbHIAAAAAAAAAAHNvdW4AAAAAAAAAAAAAAABTb3VuZEhhbmRsZXIAAAABZ21pbmYAAAAQc21oZAAAAAAAAAAAAAAAJGRpbmYAAAAcZHJlZgAAAAAAAAABAAAADHVybCAAAAABAAABJ3N0YmwAAABnc3RzZAAAAAAAAAABAAAAV21wNGEAAAAAAAAAAQAAAAAAAAAAAAIAEAAAAAooAAAAOGVzZHMAAAAAA4CAgCIAAgAEgICAFEAVAAIAAAGgAAGAjgICpOQwBQYawA==';

    return mockM4AHeader;
  }

  echoLastChunk() {
    // Echo the last received chunk back for testing
    if (this.chunkBuffer.length > 0) {
      const lastChunk = this.chunkBuffer[this.chunkBuffer.length - 1];
      const echoChunk = {
        ...lastChunk,
        index: lastChunk.index + 1000, // Offset index to avoid conflicts
        timestamp: Date.now(),
      };

      console.log(`[WebSocket] Echoing chunk ${lastChunk.index} as ${echoChunk.index}`);
      setTimeout(() => {
        this.emit('incoming_audio_chunk', echoChunk);
      }, 1000); // 1 second delay for echo
    }
  }

  stopSimulation() {
    if (this.simulationInterval) {
      clearInterval(this.simulationInterval);
      this.simulationInterval = null;
      console.log('[WebSocket] Audio simulation stopped');
    }
  }

  getConnectionState() {
    return this.connectionState;
  }

  isReady() {
    return true; // Always ready in placeholder mode
  }

  getBufferedChunks() {
    return this.chunkBuffer.length;
  }

  clearBuffer() {
    this.chunkBuffer = [];
    console.log('[WebSocket] Chunk buffer cleared');
  }
}

export default new AudioStreamingService();