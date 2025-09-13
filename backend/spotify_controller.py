import logging
import os
from typing import Optional, Dict, Any, List
import spotipy
from spotipy.oauth2 import SpotifyOAuth, SpotifyClientCredentials
from config import SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_REDIRECT_URI

logger = logging.getLogger(__name__)

class SpotifyController:
    """
    A class that handles Spotify Web API authentication and playback control.
    Keeps it simple - just search and play functionality.
    """

    def __init__(self):
        """
        Initialize the Spotify controller with API credentials.
        """
        self.client_id = SPOTIFY_CLIENT_ID
        self.client_secret = SPOTIFY_CLIENT_SECRET
        self.redirect_uri = SPOTIFY_REDIRECT_URI

        if not self.client_id or not self.client_secret:
            raise ValueError("Spotify credentials are required. Set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET environment variables.")

        # For server-side playback, we need user authentication
        # We'll use a cached token approach or implement a headless auth flow
        self.scope = "user-modify-playback-state user-read-playback-state user-read-currently-playing"
        
        # Try to use cached token first, otherwise fall back to client credentials for search only
        try:
            # Check if we have a cached token
            cache_file = ".spotify_cache"
            if os.path.exists(cache_file):
                self.sp = spotipy.Spotify(
                    auth_manager=SpotifyOAuth(
                        client_id=self.client_id,
                        client_secret=self.client_secret,
                        redirect_uri=self.redirect_uri,
                        scope=self.scope,
                        cache_path=cache_file
                    )
                )
                logger.info("Spotify controller initialized with cached user authentication")
                self.has_playback_control = True
            else:
                raise Exception("No cached token found")
                
        except Exception as e:
            logger.warning(f"Failed to initialize with user auth: {e}")
            # Fallback to client credentials (search only, no playback)
            self.sp = spotipy.Spotify(
                auth_manager=SpotifyClientCredentials(
                    client_id=self.client_id,
                    client_secret=self.client_secret
                )
            )
            logger.info("Spotify controller initialized with client credentials (search only)")
            self.has_playback_control = False

    def search_music(self, artist: Optional[str] = None, song: Optional[str] = None, album: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Search for music on Spotify using the provided criteria.

        Args:
            artist: Artist name to search for
            song: Song/track name to search for
            album: Album name to search for

        Returns:
            Dict containing the top search result or None if no results
        """
        try:
            # Build search query
            query_parts = []

            if artist:
                query_parts.append(f'artist:"{artist}"')
            if song:
                query_parts.append(f'track:"{song}"')
            if album:
                query_parts.append(f'album:"{album}"')

            if not query_parts:
                logger.warning("No search criteria provided")
                return None

            query = " ".join(query_parts)
            logger.info(f"Searching Spotify with query: {query}")

            # Search for tracks - get multiple results for better selection
            results = self.sp.search(q=query, type="track", limit=5, market="US")

            if not results["tracks"]["items"]:
                logger.info(f"No tracks found for query: {query}")

                # Try a broader search if the specific search failed
                if len(query_parts) > 1:
                    # Try with just the artist if we had multiple criteria
                    if artist:
                        broader_query = f'artist:"{artist}"'
                        logger.info(f"Trying broader search: {broader_query}")
                        results = self.sp.search(q=broader_query, type="track", limit=5, market="US")

            if not results["tracks"]["items"]:
                return None

            # Return all found tracks for better selection
            tracks = []
            for track in results["tracks"]["items"]:
                track_data = {
                    "track_uri": track["uri"],
                    "track_id": track["id"],
                    "track_name": track["name"],
                    "artist_name": track["artists"][0]["name"] if track["artists"] else "Unknown Artist",
                    "album_name": track["album"]["name"] if track["album"] else "Unknown Album",
                    "external_url": track["external_urls"].get("spotify", ""),
                    "preview_url": track.get("preview_url"),
                    "duration_ms": track.get("duration_ms", 0)
                }
                tracks.append(track_data)

            logger.info(f"Found {len(tracks)} tracks for query: {query}")
            if tracks:
                logger.info(f"Top result: {tracks[0]['track_name']} by {tracks[0]['artist_name']}")
            
            return tracks

        except Exception as e:
            logger.error(f"Error searching Spotify: {e}")
            return None

    def get_top_track(self, artist: Optional[str] = None, song: Optional[str] = None, album: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Get the top track matching the search criteria (for backward compatibility).
        
        Args:
            artist: Artist name to search for
            song: Song/track name to search for  
            album: Album name to search for
            
        Returns:
            Dict containing the top search result or None if no results
        """
        tracks = self.search_music(artist, song, album)
        if tracks and len(tracks) > 0:
            return tracks[0]
        return None

    def get_active_device(self) -> Optional[str]:
        """
        Get the currently active Spotify device ID.

        Returns:
            Device ID string or None if no active device
        """
        try:
            devices = self.sp.devices()

            # Look for active device first
            for device in devices["devices"]:
                if device["is_active"]:
                    logger.info(f"Found active device: {device['name']}")
                    return device["id"]

            # If no active device, return the first available device
            if devices["devices"]:
                device = devices["devices"][0]
                logger.info(f"No active device, using: {device['name']}")
                return device["id"]

            logger.warning("No Spotify devices found")
            return None

        except Exception as e:
            logger.error(f"Error getting devices: {e}")
            return None

    def play_track(self, track_uri: str, device_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Start playback of a specific track.

        Args:
            track_uri: Spotify track URI (e.g., "spotify:track:...")
            device_id: Specific device to play on (optional)

        Returns:
            Dict containing success status and any error messages
        """
        try:
            if not self.has_playback_control:
                return {
                    "success": False,
                    "error": "No playback control available - user authentication required",
                    "action": "search_only"
                }

            # Get device if not specified
            if not device_id:
                device_id = self.get_active_device()

            if not device_id:
                return {
                    "success": False,
                    "error": "No active Spotify device found. Please start Spotify on a device.",
                    "action": "no_device"
                }

            # Start playback
            self.sp.start_playback(uris=[track_uri], device_id=device_id)

            logger.info(f"Started playback of {track_uri} on device {device_id}")
            return {
                "success": True,
                "track_uri": track_uri,
                "device_id": device_id,
                "action": "playback_started"
            }

        except spotipy.exceptions.SpotifyException as e:
            error_msg = str(e)

            if "Premium required" in error_msg:
                return {
                    "success": False,
                    "error": "Spotify Premium subscription required for playback control",
                    "action": "premium_required"
                }
            elif "Device not found" in error_msg:
                return {
                    "success": False,
                    "error": "Spotify device not found or not available",
                    "action": "device_error"
                }
            else:
                logger.error(f"Spotify API error: {e}")
                return {
                    "success": False,
                    "error": f"Spotify playback error: {error_msg}",
                    "action": "api_error"
                }

        except Exception as e:
            logger.error(f"Unexpected error during playback: {e}")
            return {
                "success": False,
                "error": f"Unexpected playback error: {str(e)}",
                "action": "unknown_error"
            }

    def stop_playback(self, device_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Stop/pause current playback.

        Args:
            device_id: Specific device to control (optional)

        Returns:
            Dict containing success status and any error messages
        """
        try:
            if not self.has_playback_control:
                return {
                    "success": False,
                    "error": "No playback control available - user authentication required"
                }

            # Get device if not specified
            if not device_id:
                device_id = self.get_active_device()

            # Pause playback
            self.sp.pause_playback(device_id=device_id)

            logger.info(f"Stopped playback on device {device_id}")
            return {
                "success": True,
                "action": "playback_stopped"
            }

        except Exception as e:
            logger.error(f"Error stopping playback: {e}")
            return {
                "success": False,
                "error": f"Error stopping playback: {str(e)}"
            }

    async def search_and_play(self, music_request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main method: search for music and attempt to play it on the server.

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

            # Search for tracks
            tracks = self.search_music(artist=artist, song=song, album=album)

            if not tracks:
                return {
                    "success": False,
                    "error": "No tracks found matching your request",
                    "original_request": music_request,
                    "action": "no_results"
                }

            # Get the top track for playback
            top_track = tracks[0]
            
            # Attempt to play the track if we have playback control
            if self.has_playback_control:
                logger.info(f"Attempting to play: {top_track['track_name']} by {top_track['artist_name']}")
                playback_result = self.play_track(top_track["track_uri"])
                
                if playback_result["success"]:
                    result = {
                        "success": True,
                        "original_request": music_request,
                        "top_track": top_track,
                        "all_tracks": tracks,
                        "action": "music_started",
                        "message": f"Now playing: {top_track['track_name']} by {top_track['artist_name']}",
                        "playback_result": playback_result
                    }
                else:
                    result = {
                        "success": False,
                        "original_request": music_request,
                        "top_track": top_track,
                        "all_tracks": tracks,
                        "action": "playback_failed",
                        "error": playback_result.get("error", "Playback failed"),
                        "message": f"Found: {top_track['track_name']} by {top_track['artist_name']}, but playback failed: {playback_result.get('error', 'Unknown error')}",
                        "playback_result": playback_result
                    }
            else:
                # No playback control available
                result = {
                    "success": False,
                    "original_request": music_request,
                    "top_track": top_track,
                    "all_tracks": tracks,
                    "action": "no_playback_control",
                    "error": "No playback control available - user authentication required",
                    "message": f"Found: {top_track['track_name']} by {top_track['artist_name']}, but cannot control playback"
                }

            logger.info(f"Music request processed: {result['action']}")
            return result

        except Exception as e:
            logger.error(f"Error in search_and_play: {e}")
            return {
                "success": False,
                "error": f"Unexpected error: {str(e)}",
                "original_request": music_request,
                "action": "error"
            }