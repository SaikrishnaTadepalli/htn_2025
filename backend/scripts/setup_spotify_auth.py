#!/usr/bin/env python3
"""
Setup script to authenticate with Spotify for server-side playback control.
This script will help you get the necessary authentication token.
"""

import sys
import os
import webbrowser
from urllib.parse import urlparse, parse_qs
import spotipy
from spotipy.oauth2 import SpotifyOAuth

# Add the parent directory to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_REDIRECT_URI

def setup_spotify_auth():
    """Set up Spotify authentication for server-side playback."""
    
    print("🎵 Spotify Authentication Setup")
    print("=" * 40)
    
    # Check if credentials are available
    if not SPOTIFY_CLIENT_ID or not SPOTIFY_CLIENT_SECRET:
        print("❌ Spotify credentials not found!")
        print("Please set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET environment variables")
        return False
    
    print(f"✅ Spotify credentials found")
    print(f"   Client ID: {SPOTIFY_CLIENT_ID[:10]}...")
    print(f"   Redirect URI: {SPOTIFY_REDIRECT_URI}")
    print()
    
    # Check if we already have a cached token
    cache_file = ".spotify_cache"
    if os.path.exists(cache_file):
        print("🔍 Found existing cache file. Testing...")
        try:
            sp = spotipy.Spotify(
                auth_manager=SpotifyOAuth(
                    client_id=SPOTIFY_CLIENT_ID,
                    client_secret=SPOTIFY_CLIENT_SECRET,
                    redirect_uri=SPOTIFY_REDIRECT_URI,
                    scope="user-modify-playback-state user-read-playback-state user-read-currently-playing",
                    cache_path=cache_file
                )
            )
            
            # Test the connection
            user = sp.current_user()
            print(f"✅ Authentication working! Logged in as: {user.get('display_name', 'Unknown')}")
            
            # Test device access
            devices = sp.devices()
            if devices.get('devices'):
                print(f"✅ Found {len(devices['devices'])} Spotify device(s):")
                for device in devices['devices']:
                    status = "🟢 Active" if device['is_active'] else "⚪ Inactive"
                    print(f"   - {device['name']} ({device['type']}) {status}")
            else:
                print("⚠️  No Spotify devices found. Please open Spotify on any device.")
            
            return True
            
        except Exception as e:
            print(f"❌ Cached token is invalid: {e}")
            print("   Will need to re-authenticate...")
            os.remove(cache_file)
    
    print("🔐 Setting up new authentication...")
    print()
    print("This will open your browser to authorize the application.")
    print("Make sure you have Spotify open on at least one device!")
    print()
    
    input("Press Enter to continue...")
    
    try:
        # Create OAuth manager
        sp_oauth = SpotifyOAuth(
            client_id=SPOTIFY_CLIENT_ID,
            client_secret=SPOTIFY_CLIENT_SECRET,
            redirect_uri=SPOTIFY_REDIRECT_URI,
            scope="user-modify-playback-state user-read-playback-state user-read-currently-playing",
            cache_path=cache_file,
            show_dialog=True
        )
        
        # Get authorization URL
        auth_url = sp_oauth.get_authorize_url()
        print(f"🌐 Opening browser: {auth_url}")
        
        # Open browser
        webbrowser.open(auth_url)
        
        print()
        print("After authorizing in your browser, you'll be redirected to a URL.")
        print("Copy the ENTIRE URL from your browser's address bar and paste it below.")
        print()
        
        # Get the redirect URL from user
        redirect_url = input("Paste the redirect URL here: ").strip()
        
        if not redirect_url:
            print("❌ No URL provided. Authentication cancelled.")
            return False
        
        # Extract code from URL
        parsed_url = urlparse(redirect_url)
        query_params = parse_qs(parsed_url.query)
        
        if 'code' not in query_params:
            print("❌ No authorization code found in URL.")
            return False
        
        auth_code = query_params['code'][0]
        
        # Exchange code for token
        print("🔄 Exchanging authorization code for access token...")
        token_info = sp_oauth.get_access_token(auth_code)
        
        if not token_info:
            print("❌ Failed to get access token.")
            return False
        
        print("✅ Successfully authenticated!")
        
        # Test the connection
        sp = spotipy.Spotify(auth=token_info['access_token'])
        user = sp.current_user()
        print(f"✅ Logged in as: {user.get('display_name', 'Unknown')}")
        
        # Test device access
        devices = sp.devices()
        if devices.get('devices'):
            print(f"✅ Found {len(devices['devices'])} Spotify device(s):")
            for device in devices['devices']:
                status = "🟢 Active" if device['is_active'] else "⚪ Inactive"
                print(f"   - {device['name']} ({device['type']}) {status}")
        else:
            print("⚠️  No Spotify devices found. Please open Spotify on any device.")
        
        print()
        print("🎉 Authentication setup complete!")
        print("   Token cached in: .spotify_cache")
        print("   You can now use server-side Spotify playback!")
        
        return True
        
    except Exception as e:
        print(f"❌ Authentication failed: {e}")
        return False

if __name__ == "__main__":
    success = setup_spotify_auth()
    sys.exit(0 if success else 1)