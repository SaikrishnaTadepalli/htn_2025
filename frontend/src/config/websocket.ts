// Configuration for WebSocket connections
export const config = {
  websocketUrl: process.env.NEXT_PUBLIC_WEBSOCKET_URL || 'ws://localhost:8000',
}

// Helper function to get the WebSocket URL with proper protocol
export const getWebSocketUrl = (endpoint: string) => {
  const baseUrl = config.websocketUrl
  
  // If NEXT_PUBLIC_WEBSOCKET_URL is set, ensure it uses wss:// for production
  if (process.env.NEXT_PUBLIC_WEBSOCKET_URL) {
    // Remove any existing protocol
    const cleanUrl = baseUrl.replace(/^wss?:\/\//, '')
    // Always use wss:// for production environment variables
    return `wss://${cleanUrl}${endpoint}`
  }
  
  // For local development (fallback), use ws://
  const protocol = baseUrl.startsWith('wss://') ? 'wss://' : 'ws://'
  const cleanUrl = baseUrl.replace(/^wss?:\/\//, '')
  return `${protocol}${cleanUrl}${endpoint}`
}