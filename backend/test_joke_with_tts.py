#!/usr/bin/env python3
"""
Test script that combines joke_responder.py with joke_tts.py
to generate jokes and speak them out loud.
"""

import asyncio
import os
import sys
from dotenv import load_dotenv
from joke_responder import JokeResponder
from joke_tts import JokeTTS

# Load environment variables from .env file
load_dotenv()

async def test_jokes_with_tts():
    """Test the joke responder with text-to-speech functionality."""
    
    # Check for API keys
    if not os.getenv("GROQ_API_KEY"):
        print("❌ Error: GROQ_API_KEY environment variable is not set.")
        return False
    
    if not os.getenv("ELEVEN_LABS_API"):
        print("❌ Error: ELEVEN_LABS_API environment variable is not set.")
        print("Please add your ElevenLabs API key to the .env file:")
        print("ELEVEN_LABS_API=your_api_key_here")
        return False
    
    try:
        print("🚀 Initializing Joke Responder and TTS...")
        
        # Initialize components
        joke_responder = JokeResponder()
        joke_tts = JokeTTS()
        
        print("✅ Both components initialized successfully!")
        
        # Test statements that are likely to generate jokes
        test_statements = [
            "I love pizza!",
            "Why did the chicken cross the road?",
            "Tell me a joke!",
            "I'm having a terrible day.",
            "My computer is broken again.",
            "I'm hungry.",
            "This code is driving me crazy!",
            "I need a vacation.",
            "The internet is so slow today.",
            "I can't find my keys anywhere!"
        ]
        
        print(f"\n🎭 Testing {len(test_statements)} statements with TTS...")
        print("=" * 80)
        
        joke_count = 0
        spoken_count = 0
        
        for i, statement in enumerate(test_statements, 1):
            print(f"\n📝 Test {i}: '{statement}'")
            
            try:
                # Generate joke response
                joke_data = await joke_responder.process_text_for_joke(statement)
                
                if joke_data:
                    print(f"✅ Joke Generated: {joke_data['joke_response']}")
                    print(f"   Type: {joke_data['joke_type']}")
                    print(f"   Confidence: {joke_data['confidence']:.2f}")
                    
                    joke_count += 1
                    
                    # Convert to speech
                    print("🎤 Converting to speech...")
                    audio_data = await joke_tts.speak_joke(joke_data, play_audio=True)
                    
                    if audio_data:
                        print("🔊 Joke spoken successfully!")
                        spoken_count += 1
                        
                        # Save audio file
                        filename = f"joke_{i}_{joke_data['joke_type']}.mp3"
                        if joke_tts.save_audio(audio_data, filename):
                            print(f"💾 Audio saved to {filename}")
                    else:
                        print("❌ Failed to convert joke to speech")
                else:
                    print("❌ No joke generated")
                
            except Exception as e:
                print(f"❌ Error: {e}")
            
            print("-" * 60)
            
            # Small delay between tests
            await asyncio.sleep(1)
        
        # Summary
        print(f"\n📊 Test Summary:")
        print(f"   Total statements: {len(test_statements)}")
        print(f"   Jokes generated: {joke_count}")
        print(f"   Jokes spoken: {spoken_count}")
        print(f"   Joke success rate: {joke_count/len(test_statements)*100:.1f}%")
        print(f"   TTS success rate: {spoken_count/joke_count*100:.1f}%" if joke_count > 0 else "   TTS success rate: N/A")
        
        return joke_count > 0 and spoken_count > 0
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

async def test_simple_tts():
    """Test simple text-to-speech without joke generation."""
    try:
        print("\n🎤 Testing simple TTS...")
        
        tts = JokeTTS()
        
        # Test with simple text
        test_text = "Hello! This is a test of the text-to-speech system."
        print(f"Speaking: '{test_text}'")
        
        audio_data = await tts.speak_text(test_text, play_audio=True)
        
        if audio_data:
            print("✅ Simple TTS test successful!")
            return True
        else:
            print("❌ Simple TTS test failed")
            return False
            
    except Exception as e:
        print(f"❌ Simple TTS test failed: {e}")
        return False

async def main():
    """Main test function."""
    print("🎭 Joke Responder + Text-to-Speech Test")
    print("=" * 50)
    
    # Test simple TTS first
    tts_success = await test_simple_tts()
    
    if not tts_success:
        print("\n⚠️  TTS test failed. Please check your ElevenLabs API key.")
        return False
    
    # Test full integration
    integration_success = await test_jokes_with_tts()
    
    if integration_success:
        print("\n🎉 All tests passed! The joke responder with TTS is working!")
        return True
    else:
        print("\n⚠️  Some tests failed. Please check the configuration.")
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
