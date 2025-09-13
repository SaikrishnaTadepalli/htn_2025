#!/usr/bin/env python3
"""
Debug script to test ElevenLabs imports and usage.
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_imports():
    """Test ElevenLabs imports."""
    print("Testing ElevenLabs imports...")
    
    try:
        from elevenlabs import ElevenLabs
        print("✅ ElevenLabs imported successfully")
    except Exception as e:
        print(f"❌ Failed to import ElevenLabs: {e}")
        return False
    
    try:
        from elevenlabs import play
        print("✅ play imported successfully")
        print(f"play type: {type(play)}")
    except Exception as e:
        print(f"❌ Failed to import play: {e}")
        return False
    
    try:
        from elevenlabs.client import ElevenLabs as ClientElevenLabs
        print("✅ ElevenLabs from client imported successfully")
    except Exception as e:
        print(f"❌ Failed to import ElevenLabs from client: {e}")
        return False
    
    return True

def test_client_creation():
    """Test ElevenLabs client creation."""
    print("\nTesting ElevenLabs client creation...")
    
    api_key = os.getenv("ELEVEN_LABS_API")
    if not api_key:
        print("❌ ELEVEN_LABS_API not set")
        return False
    
    try:
        from elevenlabs import ElevenLabs
        client = ElevenLabs(api_key=api_key)
        print("✅ ElevenLabs client created successfully")
        return True
    except Exception as e:
        print(f"❌ Failed to create ElevenLabs client: {e}")
        return False

def test_play_function():
    """Test the play function."""
    print("\nTesting play function...")
    
    try:
        from elevenlabs import play
        print(f"play function: {play}")
        print(f"play type: {type(play)}")
        
        # Check if it's callable
        if callable(play):
            print("✅ play is callable")
        else:
            print("❌ play is not callable")
            print(f"play attributes: {dir(play)}")
        
        return callable(play)
    except Exception as e:
        print(f"❌ Error testing play function: {e}")
        return False

if __name__ == "__main__":
    print("🔍 ElevenLabs Debug Script")
    print("=" * 40)
    
    # Test imports
    import_success = test_imports()
    
    # Test client creation
    client_success = test_client_creation()
    
    # Test play function
    play_success = test_play_function()
    
    print(f"\n📊 Debug Results:")
    print(f"   Imports: {'✅' if import_success else '❌'}")
    print(f"   Client: {'✅' if client_success else '❌'}")
    print(f"   Play: {'✅' if play_success else '❌'}")
    
    if import_success and client_success and play_success:
        print("\n🎉 All tests passed!")
    else:
        print("\n⚠️  Some tests failed. Check the errors above.")
