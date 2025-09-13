#!/usr/bin/env python3
"""
Simple test script to test joke_responder.py directly without WebSocket.
This is useful for quick testing and debugging.
"""

import asyncio
import os
import sys
from dotenv import load_dotenv
from joke_responder import JokeResponder

# Load environment variables from .env file
load_dotenv()

async def test_jokes_directly():
    """Test the joke responder directly without WebSocket."""
    
    # Check for API key
    if not os.getenv("GROQ_API_KEY"):
        print("❌ Error: GROQ_API_KEY environment variable is not set.")
        print("Please set your Groq API key:")
        print("  Windows: set GROQ_API_KEY=your_api_key_here")
        print("  Linux/Mac: export GROQ_API_KEY=your_api_key_here")
        return
    
    try:
        print("🚀 Initializing JokeResponder...")
        responder = JokeResponder()
        print("✅ JokeResponder initialized!")
        
        # Test statements
        test_statements = [
            "I like apples but I hate cucumbers",
            "My barber messed up my haircut",
            "Did you hear charlie kirk passed away?",
        ]
        
        print(f"\n🧪 Testing {len(test_statements)} statements...")
        print("=" * 80)
        
        joke_count = 0
        
        for i, statement in enumerate(test_statements, 1):
            print(f"\n📝 Test {i}: '{statement}'")
            
            try:
                # Process the statement
                result = await responder.process_text_for_joke(statement)
                
                if result:
                    print(f"✅ Joke Response: {result['joke_response']}")
                    print(f"   Type: {result['joke_type']}")
                    print(f"   Confidence: {result['confidence']:.2f}")
                    print(f"   Reasoning: {result['reasoning']}")
                    joke_count += 1
                else:
                    print("❌ No joke response generated")
                
            except Exception as e:
                print(f"❌ Error: {e}")
            
            print("-" * 60)
            
            # Small delay to avoid rate limiting
            await asyncio.sleep(0.5)
        
        # Summary
        print(f"\n📊 Summary:")
        print(f"   Total statements: {len(test_statements)}")
        print(f"   Jokes generated: {joke_count}")
        print(f"   Success rate: {joke_count/len(test_statements)*100:.1f}%")
        
    except Exception as e:
        print(f"❌ Failed to initialize JokeResponder: {e}")

if __name__ == "__main__":
    print("🎭 Direct Joke Responder Test")
    print("=" * 40)
    asyncio.run(test_jokes_directly())
