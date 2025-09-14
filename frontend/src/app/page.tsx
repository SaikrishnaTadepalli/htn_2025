'use client'

import { useEffect, useRef, useState } from 'react'
import { getWebSocketUrl } from '../config/websocket'

export default function Home() {
  const videoRef = useRef<HTMLVideoElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const audioContextRef = useRef<AudioContext | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const processorRef = useRef<any>(null)
  const currentAudioRef = useRef<HTMLAudioElement | null>(null)
  const frameIntervalRef = useRef<NodeJS.Timeout | null>(null)

  const [transcription, setTranscription] = useState('')
  const [jokeResponse, setJokeResponse] = useState('')
  const [isConnected, setIsConnected] = useState(false)
  const [, setIsPlayingAudio] = useState(false)
  const [currentExpression, setCurrentExpression] = useState<{
    expression: string
    emoji: string
    confidence: number
  } | null>(null)
  const [isPlayingFacialJoke, setIsPlayingFacialJoke] = useState(false)

  // Streaming audio state
  const streamingAudioRef = useRef<{
    chunks: Uint8Array[]
    expectedChunks?: number
    sessionId: string
    type: string
  } | null>(null)

  // Helper function to play streaming audio
  const playStreamingAudio = (chunks: Uint8Array[], audioType: string) => {
    try {
      // Combine all chunks into one array
      const totalLength = chunks.reduce((sum, chunk) => sum + chunk.length, 0)
      const combinedArray = new Uint8Array(totalLength)
      let offset = 0

      chunks.forEach(chunk => {
        combinedArray.set(chunk, offset)
        offset += chunk.length
      })

      const audioBlob = new Blob([combinedArray], { type: 'audio/mpeg' })
      const audioUrl = URL.createObjectURL(audioBlob)

      if (currentAudioRef.current) {
        currentAudioRef.current.pause()
        currentAudioRef.current.currentTime = 0
      }

      const audio = new Audio(audioUrl)
      audio.preload = 'auto'
      audio.crossOrigin = 'anonymous'

      currentAudioRef.current = audio
      setIsPlayingAudio(true)

      if (audioType.includes('facial')) {
        setIsPlayingFacialJoke(true)
      }

      audio.onended = () => {
        setIsPlayingAudio(false)
        setIsPlayingFacialJoke(false)
        currentAudioRef.current = null
        URL.revokeObjectURL(audioUrl)
      }

      audio.onerror = (error) => {
        console.error('Streaming audio element error:', error)
        setIsPlayingAudio(false)
        setIsPlayingFacialJoke(false)
        currentAudioRef.current = null
        URL.revokeObjectURL(audioUrl)
      }

      const playPromise = audio.play()
      if (playPromise !== undefined) {
        playPromise.catch(error => {
          console.error('Streaming audio play failed:', error)
          setIsPlayingAudio(false)
          setIsPlayingFacialJoke(false)
        })
      }

      console.log(`Playing streaming ${audioType} audio: ${chunks.length} chunks combined`)

    } catch (e) {
      console.error('Error playing streaming audio:', e)
      setIsPlayingAudio(false)
      setIsPlayingFacialJoke(false)
    }
  }

  // Function to capture and send video frames
  const captureAndSendFrame = (sessionId: string, ws: WebSocket) => {
    if (!videoRef.current || !canvasRef.current || ws.readyState !== WebSocket.OPEN) {
      return
    }

    try {
      const video = videoRef.current
      const canvas = canvasRef.current
      const ctx = canvas.getContext('2d')

      if (!ctx || video.readyState < 2) {
        return // Video not ready
      }

      // Set canvas size for optimal MediaPipe processing (square aspect ratio)
      canvas.width = 416
      canvas.height = 416

      // Draw video frame to canvas (will automatically scale/crop)
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height)

      // Convert canvas to blob and then to base64
      canvas.toBlob((blob) => {
        if (blob) {
          const reader = new FileReader()
          reader.onload = () => {
            const base64Data = reader.result as string
            const frameData = base64Data.split(',')[1] // Remove data:image/jpeg;base64, prefix

            // Send frame data to backend
            ws.send(JSON.stringify({
              type: 'video_frame',
              session_id: sessionId,
              frame_data: frameData,
              timestamp: Date.now()
            }))
          }
          reader.readAsDataURL(blob)
        }
      }, 'image/jpeg', 0.8) // JPEG with 80% quality for balance of size/quality

    } catch (error) {
      console.error('Error capturing frame:', error)
    }
  }

  useEffect(() => {
    const startEverything = async () => {
      try {
        // Get camera and microphone
        const stream = await navigator.mediaDevices.getUserMedia({
          video: { width: 1280, height: 720 },
          audio: {
            sampleRate: 16000,
            channelCount: 1,
            echoCancellation: true,
            noiseSuppression: true
          }
        })
        streamRef.current = stream

        // Set up video
        if (videoRef.current) {
          videoRef.current.srcObject = stream
        }

        // Connect WebSocket
        const sessionId = `session_${Date.now()}`
        const ws = new WebSocket(getWebSocketUrl('/ws/audio'))
        wsRef.current = ws

        ws.onopen = () => {
          setIsConnected(true)
          ws.send(JSON.stringify({
            type: 'session_start',
            session_id: sessionId
          }))

          // Start sending video frames every 2 seconds (aligned with audio processing)
          frameIntervalRef.current = setInterval(() => {
            captureAndSendFrame(sessionId, ws)
          }, 2000)
        }

        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data)
            console.log('Received message:', data.type, data)

            if (data.type === 'transcription') {
              setTranscription(data.text || '')
            } else if (data.type === 'joke_response') {
              setJokeResponse(data.joke || '')
              setTranscription(data.original_text || '')
            } else if (data.type === 'music_response') {
              setJokeResponse(data.joke_message || '')
              setTranscription(data.original_text || '')
            } else if (data.type === 'joke_tts_failed') {
              setJokeResponse(data.joke_text || '')
            } else if (data.type === 'expression_result') {
              // Update current expression state
              if (data.face_detected) {
                setCurrentExpression({
                  expression: data.expression || 'neutral',
                  emoji: data.emoji || '😐',
                  confidence: data.confidence || 0
                })
              } else {
                setCurrentExpression(null)
              }

              // Display facial joke if present
              if (data.facial_joke) {
                setJokeResponse(data.facial_joke)

                // If streaming is enabled, prepare to collect chunks
                if (data.facial_joke_streaming) {
                  streamingAudioRef.current = {
                    chunks: [],
                    sessionId: data.session_id,
                    type: 'facial_joke'
                  }
                  console.log('Started collecting facial joke audio chunks')
                }
              }

              // Handle facial joke audio if present (non-streaming)
              if (data.facial_joke_audio && !data.facial_joke_streaming) {
                if (currentAudioRef.current) {
                  currentAudioRef.current.pause()
                  currentAudioRef.current.currentTime = 0
                }

                // Play facial joke audio
                try {
                  const audioData = atob(data.facial_joke_audio)

                  const audioBytes = new Uint8Array(audioData.length)
                  for (let i = 0; i < audioData.length; i++) {
                    audioBytes[i] = audioData.charCodeAt(i)
                  }

                  const audioBlob = new Blob([audioBytes], { type: 'audio/mpeg' })
                  const audioUrl = URL.createObjectURL(audioBlob)

                  const audio = new Audio(audioUrl)

                  // Set additional properties for better compatibility
                  audio.preload = 'auto'
                  audio.crossOrigin = 'anonymous'

                  currentAudioRef.current = audio
                  setIsPlayingAudio(true)
                  setIsPlayingFacialJoke(true)

                  audio.onended = () => {
                    setIsPlayingAudio(false)
                    setIsPlayingFacialJoke(false)
                    currentAudioRef.current = null
                    URL.revokeObjectURL(audioUrl)
                  }

                  audio.onerror = (error) => {
                    console.error('Facial joke audio element error:', error)
                    setIsPlayingAudio(false)
                    setIsPlayingFacialJoke(false)
                    currentAudioRef.current = null
                    URL.revokeObjectURL(audioUrl)
                  }

                  const playPromise = audio.play()
                  if (playPromise !== undefined) {
                    playPromise.catch(error => {
                      console.error('Facial joke audio play failed:', error)
                      setIsPlayingAudio(false)
                      setIsPlayingFacialJoke(false)

                      // Try alternative approach: force load first
                      audio.load()
                      setTimeout(() => {
                        audio.play().catch(() => {
                          setIsPlayingAudio(false)
                          setIsPlayingFacialJoke(false)
                        })
                      }, 100)
                    })
                  }
                } catch (e) {
                  console.error('Error playing facial joke audio:', e)
                  setIsPlayingAudio(false)
                  setIsPlayingFacialJoke(false)
                }
              }
            } else if ((data.type === 'joke_audio' || data.type === 'music_audio') && data.audio_data) {
              if (currentAudioRef.current) {
                currentAudioRef.current.pause()
                currentAudioRef.current.currentTime = 0
              }

              // Play new joke audio
              try {
                const audioData = atob(data.audio_data)

                const audioBytes = new Uint8Array(audioData.length)
                for (let i = 0; i < audioData.length; i++) {
                  audioBytes[i] = audioData.charCodeAt(i)
                }

                const audioBlob = new Blob([audioBytes], { type: 'audio/mpeg' })
                const audioUrl = URL.createObjectURL(audioBlob)

                const audio = new Audio(audioUrl)

                // Set additional properties for better compatibility
                audio.preload = 'auto'
                audio.crossOrigin = 'anonymous'

                currentAudioRef.current = audio
                setIsPlayingAudio(true)

                audio.onended = () => {
                  setIsPlayingAudio(false)
                  currentAudioRef.current = null
                  URL.revokeObjectURL(audioUrl)
                }

                audio.onerror = (error) => {
                  console.error('Audio element error:', error)
                  setIsPlayingAudio(false)
                  currentAudioRef.current = null
                  URL.revokeObjectURL(audioUrl)
                }

                const playPromise = audio.play()
                if (playPromise !== undefined) {
                  playPromise.catch(error => {
                    console.error('Audio play failed:', error)
                    setIsPlayingAudio(false)

                    // Try alternative approach: force load first
                    audio.load()
                    setTimeout(() => {
                      audio.play().catch(() => setIsPlayingAudio(false))
                    }, 100)
                  })
                }
              } catch (e) {
                console.error('Error playing audio:', e)
                setIsPlayingAudio(false)
              }
            } else if (data.type === 'joke_response' && data.streaming) {
              // Handle streaming joke response - display text immediately
              setJokeResponse(data.joke_text || '')
              setTranscription(data.original_text || '')

              // Prepare to collect streaming audio chunks
              streamingAudioRef.current = {
                chunks: [],
                sessionId: data.session_id,
                type: 'joke'
              }
              console.log('Started collecting joke audio chunks')

            } else if (data.type === 'joke_audio_chunk' || data.type === 'facial_joke_audio_chunk') {
              // Handle streaming audio chunks
              console.log('Processing audio chunk, streamingAudioRef status:', streamingAudioRef.current)

              if (streamingAudioRef.current && streamingAudioRef.current.sessionId === data.session_id) {
                try {
                  const chunkData = atob(data.chunk_data)
                  const chunkBytes = new Uint8Array(chunkData.length)
                  for (let i = 0; i < chunkData.length; i++) {
                    chunkBytes[i] = chunkData.charCodeAt(i)
                  }

                  streamingAudioRef.current.chunks.push(chunkBytes)
                  console.log(`Received audio chunk ${data.chunk_index}: ${chunkBytes.length} bytes (total chunks: ${streamingAudioRef.current.chunks.length})`)
                } catch (e) {
                  console.error('Error processing audio chunk:', e)
                }
              } else {
                console.warn('Received audio chunk but streamingAudioRef not set up:', {
                  hasStreamingRef: !!streamingAudioRef.current,
                  expectedSession: streamingAudioRef.current?.sessionId,
                  receivedSession: data.session_id
                })

                // Emergency fallback: set up streaming ref if missing
                if (!streamingAudioRef.current) {
                  streamingAudioRef.current = {
                    chunks: [],
                    sessionId: data.session_id,
                    type: 'joke'
                  }
                  console.log('Emergency: Created streamingAudioRef for session:', data.session_id)
                }
              }

            } else if (data.type === 'joke_audio_end' || data.type === 'facial_joke_audio_end') {
              // Audio streaming complete - play combined chunks
              if (streamingAudioRef.current && streamingAudioRef.current.sessionId === data.session_id) {
                console.log(`Audio streaming complete: ${data.total_chunks} chunks received`)

                playStreamingAudio(streamingAudioRef.current.chunks, streamingAudioRef.current.type)

                // Clean up
                streamingAudioRef.current = null
              }
            }
          } catch (e) {
            console.error('Error parsing message:', e)
          }
        }

        // Set up audio processing
        const audioContext = new AudioContext({ sampleRate: 16000 })
        audioContextRef.current = audioContext

        const source = audioContext.createMediaStreamSource(stream)
        const processor = audioContext.createScriptProcessor(8192, 1, 1)
        processorRef.current = processor

        processor.onaudioprocess = (event: AudioProcessingEvent) => {
          if (ws.readyState === WebSocket.OPEN) {
            const inputData = event.inputBuffer.getChannelData(0)

            // Convert to int16
            const int16Data = new Int16Array(inputData.length)
            for (let i = 0; i < inputData.length; i++) {
              const clampedValue = Math.max(-1, Math.min(1, inputData[i]))
              int16Data[i] = clampedValue * 32767
            }

            // Send to backend
            const audioData = btoa(String.fromCharCode(...new Uint8Array(int16Data.buffer)))
            ws.send(JSON.stringify({
              type: 'audio_chunk',
              session_id: sessionId,
              audio_data: audioData,
              timestamp: Date.now()
            }))
          }
        }

        source.connect(processor)
        processor.connect(audioContext.destination)

      } catch (error) {
        console.error('Failed to start:', error)
      }
    }

    startEverything()

    return () => {
      // Cleanup
      if (frameIntervalRef.current) {
        clearInterval(frameIntervalRef.current)
      }
      if (currentAudioRef.current) {
        currentAudioRef.current.pause()
        currentAudioRef.current = null
      }
      if (processorRef.current) {
        processorRef.current.disconnect()
      }
      if (audioContextRef.current) {
        audioContextRef.current.close()
      }
      if (streamRef.current) {
        streamRef.current.getTracks().forEach(track => track.stop())
      }
      if (wsRef.current) {
        wsRef.current.close()
      }
    }
  }, [])

  return (
    <div className="relative w-screen h-screen bg-black overflow-hidden">
      {/* Full screen video */}
      <video
        ref={videoRef}
        autoPlay
        muted
        className="w-full h-full object-cover"
      />

      {/* Hidden canvas for frame capture */}
      <canvas
        ref={canvasRef}
        className="hidden"
        width={416}
        height={416}
      />

      {/* Status indicators */}
      <div className="absolute top-4 right-4 space-y-2">
        {/* Connection status */}
        <div className={`px-3 py-1 rounded-full text-sm font-medium ${
          isConnected ? 'bg-green-500 text-white' : 'bg-red-500 text-white'
        }`}>
          {isConnected ? 'Connected' : 'Disconnected'}
        </div>

        {/* Expression indicator */}
        {currentExpression && (
          <div className="bg-purple-500 text-white px-3 py-1 rounded-full text-sm font-medium flex items-center space-x-2">
            <span className="text-lg">{currentExpression.emoji}</span>
            <span>{currentExpression.expression}</span>
            <span className="text-xs opacity-75">
              ({Math.round(currentExpression.confidence * 100)}%)
            </span>
          </div>
        )}

        {/* Facial joke playing indicator */}
        {isPlayingFacialJoke && (
          <div className="bg-pink-500 text-white px-3 py-1 rounded-full text-sm font-medium flex items-center space-x-2 animate-pulse">
            <span className="text-lg">🎭</span>
            <span>Facial Joke Playing</span>
          </div>
        )}
      </div>

      {/* Caption overlay */}
      <div className="absolute bottom-0 left-0 right-0 bg-black bg-opacity-70 text-white p-6">
        {/* Transcription */}
        <div className="mb-2">
          <div className="text-lg font-medium">
            {transcription || 'Listening...'}
          </div>
        </div>

        {/* Joke response */}
        {jokeResponse && (
          <div className="text-yellow-300 text-xl font-bold">
            🎭 {jokeResponse}
          </div>
        )}
      </div>
    </div>
  )
}