#!/usr/bin/env python3
"""
Simple test script for the TTS functionality only.
This tests the ElevenLabs integration without joke generation.
"""

import asyncio
import os
import sys
from dotenv import load_dotenv
from joke_tts import JokeTTS

# Load environment variables from .env file
load_dotenv()

async def test_tts():
    """Test the TTS functionality."""
    
    # Check for ElevenLabs API key
    if not os.getenv("ELEVEN_LABS_API"):
        print("❌ Error: ELEVEN_LABS_API environment variable is not set.")
        print("Please add your ElevenLabs API key to the .env file:")
        print("ELEVEN_LABS_API=your_api_key_here")
        return False
    
    try:
        print("🎤 Testing ElevenLabs TTS...")
        
        # Initialize TTS
        tts = JokeTTS()
        print("✅ TTS initialized successfully!")
        
        # Test with sample texts
        test_texts = [
            "Hello! This is a test of the text-to-speech system.",
            "I love pizza! In fact, I'm so passionate about it that I've been known to go on pizza dates with myself!",
            "Why did the chicken cross the road? To get to the other side, of course!",
            "My computer is broken again. I guess that's one way to get a free parking spot!",
            "I need a vacation. Maybe I should just take a mental health day and call it a 'brain vacation'!"
        ]
        
        print(f"\n🔊 Testing {len(test_texts)} texts...")
        print("=" * 60)
        
        success_count = 0
        
        for i, text in enumerate(test_texts, 1):
            print(f"\n📝 Test {i}: '{text}'")
            
            try:
                # Convert to speech
                audio_data = await tts.speak_text(text, play_audio=True)
                
                if audio_data:
                    print("✅ Text converted to speech successfully!")
                    success_count += 1
                    
                    # Save audio file
                    filename = f"tts_test_{i}.mp3"
                    if tts.save_audio(audio_data, filename):
                        print(f"💾 Audio saved to {filename}")
                else:
                    print("❌ Failed to convert text to speech")
                
            except Exception as e:
                print(f"❌ Error: {e}")
            
            print("-" * 40)
            
            # Small delay between tests
            await asyncio.sleep(1)
        
        # Summary
        print(f"\n📊 Test Summary:")
        print(f"   Total texts: {len(test_texts)}")
        print(f"   Successful conversions: {success_count}")
        print(f"   Success rate: {success_count/len(test_texts)*100:.1f}%")
        
        return success_count > 0
        
    except Exception as e:
        print(f"❌ TTS test failed: {e}")
        return False

if __name__ == "__main__":
    print("🎤 ElevenLabs TTS Test")
    print("=" * 30)
    
    success = asyncio.run(test_tts())
    
    if success:
        print("\n🎉 TTS test completed successfully!")
    else:
        print("\n⚠️  TTS test failed. Please check your ElevenLabs API key.")
    
    sys.exit(0 if success else 1)
