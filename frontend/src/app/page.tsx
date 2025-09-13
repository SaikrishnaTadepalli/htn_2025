'use client'

import { useEffect, useRef, useState } from 'react'

export default function Home() {
  const videoRef = useRef<HTMLVideoElement>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const audioContextRef = useRef<AudioContext | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const processorRef = useRef<any>(null)

  const [transcription, setTranscription] = useState('')
  const [jokeResponse, setJokeResponse] = useState('')
  const [isConnected, setIsConnected] = useState(false)

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
        const ws = new WebSocket('ws://localhost:8000/ws/audio')
        wsRef.current = ws

        ws.onopen = () => {
          setIsConnected(true)
          ws.send(JSON.stringify({
            type: 'session_start',
            session_id: sessionId
          }))
        }

        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data)

            if (data.type === 'transcription') {
              setTranscription(data.text || '')
            } else if (data.type === 'joke_response') {
              setJokeResponse(data.joke || '')
              setTranscription(data.original_text || '')
            } else if (data.type === 'joke_audio' && data.audio_data) {
              // Play joke audio
              try {
                const audioData = atob(data.audio_data)
                const audioBytes = new Uint8Array(audioData.length)
                for (let i = 0; i < audioData.length; i++) {
                  audioBytes[i] = audioData.charCodeAt(i)
                }
                const audioBlob = new Blob([audioBytes], { type: 'audio/mp3' })
                const audioUrl = URL.createObjectURL(audioBlob)
                const audio = new Audio(audioUrl)
                audio.play()
              } catch (e) {
                console.error('Error playing audio:', e)
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

      {/* Connection status */}
      <div className="absolute top-4 right-4">
        <div className={`px-3 py-1 rounded-full text-sm font-medium ${
          isConnected ? 'bg-green-500 text-white' : 'bg-red-500 text-white'
        }`}>
          {isConnected ? 'Connected' : 'Disconnected'}
        </div>
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