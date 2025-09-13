#!/usr/bin/env python3
"""
Test script for the JokeResponder functionality.
This script tests the joke responder without requiring a WebSocket connection.
"""

import asyncio
import os
import sys
import logging
from joke_responder import JokeResponder

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_joke_responder():
    """Test the JokeResponder class with various input texts."""
    
    # Check if GROQ_API_KEY is set
    if not os.getenv("GROQ_API_KEY"):
        print("❌ Error: GROQ_API_KEY environment variable is not set.")
        print("Please set your Groq API key:")
        print("  Windows: set GROQ_API_KEY=your_api_key_here")
        print("  Linux/Mac: export GROQ_API_KEY=your_api_key_here")
        return False
    
    try:
        # Initialize the joke responder
        print("🚀 Initializing JokeResponder...")
        responder = JokeResponder()
        print("✅ JokeResponder initialized successfully!")
        
        # Test cases with different types of inputs
        test_cases = [
            {
                "text": "What's the weather like today?",
                "description": "Weather question - should trigger joke"
            },
            {
                "text": "I'm feeling really sad about my job.",
                "description": "Sad statement - might trigger supportive humor"
            },
            {
                "text": "Why did the chicken cross the road?",
                "description": "Already a joke - should trigger response"
            },
            {
                "text": "Can you help me with this math problem?",
                "description": "Serious question - might not trigger joke"
            },
            {
                "text": "I love pizza!",
                "description": "Positive statement - should trigger joke"
            },
            {
                "text": "My computer is broken again.",
                "description": "Frustrating situation - should trigger joke"
            },
            {
                "text": "What's 2+2?",
                "description": "Simple math - probably won't trigger joke"
            },
            {
                "text": "Tell me a joke!",
                "description": "Direct request for joke - should definitely trigger"
            }
        ]
        
        print(f"\n🧪 Testing {len(test_cases)} different input texts...\n")
        
        results = []
        
        for i, test_case in enumerate(test_cases, 1):
            text = test_case["text"]
            description = test_case["description"]
            
            print(f"Test {i}: {description}")
            print(f"Input: '{text}'")
            
            try:
                # Process the text for potential joke response
                result = await responder.process_text_for_joke(text)
                
                if result:
                    print(f"✅ Joke Response: {result['joke_response']}")
                    print(f"   Type: {result['joke_type']}")
                    print(f"   Confidence: {result['confidence']:.2f}")
                    print(f"   Reasoning: {result['reasoning']}")
                    results.append({
                        "input": text,
                        "joke_response": result['joke_response'],
                        "confidence": result['confidence'],
                        "joke_type": result['joke_type']
                    })
                else:
                    print("❌ No joke response generated")
                    results.append({
                        "input": text,
                        "joke_response": None,
                        "confidence": 0.0,
                        "joke_type": "none"
                    })
                
            except Exception as e:
                print(f"❌ Error processing text: {e}")
                results.append({
                    "input": text,
                    "joke_response": None,
                    "confidence": 0.0,
                    "joke_type": "error"
                })
            
            print("-" * 60)
        
        # Summary
        successful_jokes = sum(1 for r in results if r['joke_response'] is not None)
        total_tests = len(results)
        
        print(f"\n📊 Test Summary:")
        print(f"   Total tests: {total_tests}")
        print(f"   Successful jokes: {successful_jokes}")
        print(f"   Success rate: {successful_jokes/total_tests*100:.1f}%")
        
        # Show joke types distribution
        joke_types = {}
        for result in results:
            if result['joke_response']:
                joke_type = result['joke_type']
                joke_types[joke_type] = joke_types.get(joke_type, 0) + 1
        
        if joke_types:
            print(f"\n🎭 Joke Types Generated:")
            for joke_type, count in joke_types.items():
                print(f"   {joke_type}: {count}")
        
        return successful_jokes > 0
        
    except Exception as e:
        print(f"❌ Failed to initialize JokeResponder: {e}")
        return False

async def test_websocket_message_handling():
    """Test the WebSocket message handling functionality."""
    
    print("\n🔌 Testing WebSocket message handling...")
    
    try:
        responder = JokeResponder()
        
        # Test different WebSocket message formats
        test_messages = [
            {
                "type": "transcription",
                "text": "Hello there!",
                "session_id": "test_session"
            },
            {
                "type": "text_message",
                "content": "How are you doing?",
                "session_id": "test_session"
            },
            {
                "text": "What's up?",
                "session_id": "test_session"
            }
        ]
        
        for i, message in enumerate(test_messages, 1):
            print(f"\nWebSocket Test {i}: {message['type'] if 'type' in message else 'no_type'}")
            print(f"Message: {message}")
            
            result = await responder.handle_websocket_message(message)
            
            if result:
                print(f"✅ Generated response: {result['joke_response']}")
            else:
                print("❌ No response generated")
        
        return True
        
    except Exception as e:
        print(f"❌ WebSocket message handling test failed: {e}")
        return False

async def main():
    """Main test function."""
    print("🎭 JokeResponder Test Suite")
    print("=" * 50)
    
    # Test basic functionality
    basic_test_passed = await test_joke_responder()
    
    # Test WebSocket message handling
    websocket_test_passed = await test_websocket_message_handling()
    
    print("\n" + "=" * 50)
    print("🏁 Test Results:")
    print(f"   Basic functionality: {'✅ PASSED' if basic_test_passed else '❌ FAILED'}")
    print(f"   WebSocket handling: {'✅ PASSED' if websocket_test_passed else '❌ FAILED'}")
    
    if basic_test_passed and websocket_test_passed:
        print("\n🎉 All tests passed! The JokeResponder is ready to use.")
        return True
    else:
        print("\n⚠️  Some tests failed. Please check the configuration and try again.")
        return False

if __name__ == "__main__":
    # Run the tests
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
