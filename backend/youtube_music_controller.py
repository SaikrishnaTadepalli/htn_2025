import logging
import subprocess
import requests
import signal
import asyncio
from typing import Optional, Dict, Any
from yt_dlp import YoutubeDL

logger = logging.getLogger(__name__)

class YouTubeMusicController:
    """
    A simplified music controller that uses YouTube and yt-dlp for music playback.
    No authentication required - just search and play!
    """

    def __init__(self):
        """Initialize the YouTube music controller."""
        logger.info("YouTube Music Controller initialized")
        self.current_process = None

    def _build_search_query(self, artist: Optional[str] = None, song: Optional[str] = None, album: Optional[str] = None) -> str:
        """
        Build an effective search query for YouTube music.
        
        Args:
            artist: Artist name
            song: Song name  
            album: Album name
            
        Returns:
            Search query string
        """
        query_parts = []
        
        # Add song first if available (most specific)
        if song:
            query_parts.append(song)
        
        # Add artist
        if artist:
            query_parts.append(artist)
            
        # Add album if available
        if album:
            query_parts.append(album)
        
        # Join with commas for better YouTube search results
        query = ",".join(query_parts)
        
        logger.info(f"Built search query: {query}")
        return query

    async def search_and_play(self, music_request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main method: search for music on YouTube and play it.
        
        Args:
            music_request: Parsed music request from SpotifyResponder
            
        Returns:
            Dict containing the result of the search and play attempt
        """
        try:
            # Extract search parameters
            artist = music_request.get("artist")
            song = music_request.get("song") 
            album = music_request.get("album")
            
            logger.info(f"Processing music request - Artist: {artist}, Song: {song}, Album: {album}")
            
            # Build search query
            search_query = self._build_search_query(artist, song, album)
            
            if not search_query:
                return {
                    "success": False,
                    "error": "No search criteria provided",
                    "original_request": music_request,
                    "action": "no_query"
                }
            
            # Search for the music (but don't play yet)
            result = await self._search_music_only(search_query)
            
            if result["success"]:
                # Create a fun message that will be read aloud
                import random
                music_messages = [
                    "Time to get the party started! Let me queue up some tunes for you.",
                    "Alright, let's turn up the volume and get some music pumping!",
                    "Perfect! I'm going to blast some awesome music for you right now.",
                    "Music time! Let me find something that'll get your groove on.",
                    "Here we go! Time to fill the air with some sweet sounds.",
                    "Boom! Let me crank up some music that'll make your day better.",
                    "Alright alright, let's get this musical party started!",
                    "Music incoming! Prepare for some audio awesomeness."
                ]
                
                response = {
                    "success": True,
                    "original_request": music_request,
                    "search_query": search_query,
                    "action": "music_found",
                    "message": f"Found: {result.get('title', 'Unknown track')}",
                    "joke_message": random.choice(music_messages),  # This gets read aloud
                    "title": result.get("title", "Unknown"),
                    "track_info": result  # Store track info for later playback
                }
            else:
                response = {
                    "success": False,
                    "original_request": music_request,
                    "search_query": search_query,
                    "action": "playback_failed",
                    "error": result.get("error", "Playback failed"),
                    "message": f"Found music but playback failed: {result.get('error', 'Unknown error')}"
                }
            
            logger.info(f"Music request processed: {response['action']}")
            return response
            
        except Exception as e:
            logger.error(f"Error in search_and_play: {e}")
            return {
                "success": False,
                "error": f"Unexpected error: {str(e)}",
                "original_request": music_request,
                "action": "error"
            }

    async def start_playback(self, track_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Start the actual music playback using the track info from search.
        
        Args:
            track_info: Track information from search
            
        Returns:
            Dict containing playback result
        """
        try:
            logger.info(f"Starting playback of: {track_info.get('title', 'Unknown')}")
            
            # Start playback in background
            await self._start_playback(track_info["url"], track_info["headers"], track_info["title"])
            
            return {
                "success": True,
                "action": "playback_started",
                "message": f"Now playing: {track_info.get('title', 'Unknown')}"
            }
            
        except Exception as e:
            logger.error(f"Error starting playback: {e}")
            return {
                "success": False,
                "error": f"Playback error: {str(e)}"
            }

    async def _search_music_only(self, query: str) -> Dict[str, Any]:
        """
        Search for music on YouTube without starting playback.
        
        Args:
            query: Search query string
            
        Returns:
            Dict containing track info
        """
        try:
            logger.info(f"Searching YouTube for: {query}")
            
            # Configure yt-dlp options
            ydl_opts = {
                "quiet": True,
                "noplaylist": True,
                "format": "bestaudio/best",
            }
            
            # Search for the track
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(f"ytsearch1:{query}", download=False)
                if "entries" in info and info["entries"]:
                    track_info = info["entries"][0]
                else:
                    return {
                        "success": False,
                        "error": "No tracks found for search query"
                    }
                
                title = track_info.get("title", "Unknown")
                url = track_info["url"]
                headers = track_info.get("http_headers", {}) or {}
            
            logger.info(f"Found track: {title}")
            
            return {
                "success": True,
                "title": title,
                "url": url,
                "headers": headers
            }
            
        except Exception as e:
            logger.error(f"Error searching music: {e}")
            return {
                "success": False,
                "error": f"Search error: {str(e)}"
            }

    async def _play_music(self, query: str) -> Dict[str, Any]:
        """
        Search for and play music on YouTube using yt-dlp and ffplay.
        
        Args:
            query: Search query string
            
        Returns:
            Dict containing success status and track info
        """
        try:
            logger.info(f"Searching YouTube for: {query}")
            
            # Configure yt-dlp options
            ydl_opts = {
                "quiet": True,
                "noplaylist": True,
                "format": "bestaudio/best",
            }
            
            # Search for the track
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(f"ytsearch1:{query}", download=False)
                if "entries" in info and info["entries"]:
                    track_info = info["entries"][0]
                else:
                    return {
                        "success": False,
                        "error": "No tracks found for search query"
                    }
                
                title = track_info.get("title", "Unknown")
                url = track_info["url"]
                headers = track_info.get("http_headers", {}) or {}
            
            logger.info(f"Found track: {title}")
            logger.info(f"Starting playback...")
            
            # Start playback in background
            await self._start_playback(url, headers, title)
            
            return {
                "success": True,
                "title": title,
                "url": url
            }
            
        except Exception as e:
            logger.error(f"Error playing music: {e}")
            return {
                "success": False,
                "error": f"Playback error: {str(e)}"
            }

    async def _start_playback(self, url: str, headers: Dict[str, str], title: str):
        """
        Start audio playback using ffplay in the background.
        
        Args:
            url: Audio stream URL
            headers: HTTP headers for the request
            title: Track title for logging
        """
        try:
            # Stop any existing playback
            await self.stop_playback()
            
            logger.info(f"Starting playback of: {title}")
            
            # Start ffplay process
            self.current_process = subprocess.Popen(
                ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", "-i", "-"],
                stdin=subprocess.PIPE
            )
            
            # Set up signal handler for cleanup
            def cleanup(*_):
                if self.current_process and self.current_process.stdin:
                    self.current_process.stdin.close()
                if self.current_process:
                    self.current_process.terminate()
                self.current_process = None
            
            signal.signal(signal.SIGINT, cleanup)
            
            # Stream audio data to ffplay
            def stream_audio():
                try:
                    with requests.get(url, headers=headers, stream=True) as r:
                        r.raise_for_status()
                        for chunk in r.iter_content(chunk_size=64 * 1024):
                            if chunk and self.current_process and self.current_process.stdin:
                                self.current_process.stdin.write(chunk)
                            elif not self.current_process:
                                break  # Process was stopped
                    
                    if self.current_process and self.current_process.stdin:
                        self.current_process.stdin.close()
                        self.current_process.wait()
                        self.current_process = None
                        
                except Exception as e:
                    logger.error(f"Error streaming audio: {e}")
                    cleanup()
            
            # Run streaming in a separate thread
            import threading
            stream_thread = threading.Thread(target=stream_audio, daemon=True)
            stream_thread.start()
            
        except Exception as e:
            logger.error(f"Error starting playback: {e}")
            raise

    async def stop_playback(self) -> Dict[str, Any]:
        """
        Stop current music playback.
        
        Returns:
            Dict containing success status
        """
        try:
            if self.current_process:
                logger.info("Stopping current playback...")
                
                if self.current_process.stdin:
                    self.current_process.stdin.close()
                self.current_process.terminate()
                self.current_process.wait()
                self.current_process = None
                
                return {
                    "success": True,
                    "action": "playback_stopped",
                    "message": "Music stopped"
                }
            else:
                return {
                    "success": False,
                    "action": "no_playback",
                    "message": "No music currently playing"
                }
                
        except Exception as e:
            logger.error(f"Error stopping playback: {e}")
            return {
                "success": False,
                "error": f"Error stopping playback: {str(e)}"
            }

    def is_playing(self) -> bool:
        """
        Check if music is currently playing.
        
        Returns:
            True if music is playing, False otherwise
        """
        return self.current_process is not None and self.current_process.poll() is None