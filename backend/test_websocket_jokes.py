#!/usr/bin/env python3
"""
Test script to connect to the WebSocket and test joke responses with various statements.
This script will connect to the text WebSocket endpoint and send test messages.
"""

import asyncio
import websockets
import json
import logging
import time
from typing import List, Dict
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class WebSocketJokeTester:
    def __init__(self, websocket_url: str = "ws://localhost:8000/ws/text"):
        self.websocket_url = websocket_url
        self.session_id = f"test_session_{int(time.time())}"
        
    async def connect_and_test(self):
        """Connect to WebSocket and run test messages."""
        try:
            async with websockets.connect(self.websocket_url) as websocket:
                logger.info(f"Connected to {self.websocket_url}")
                
                # Start session
                await self.start_session(websocket)
                
                # Wait a moment for session to be ready
                await asyncio.sleep(1)
                
                # Run test messages
                await self.run_test_messages(websocket)
                
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            print(f"❌ Failed to connect to {self.websocket_url}")
            print("Make sure the server is running with: python main.py")
    
    async def start_session(self, websocket):
        """Start a WebSocket session."""
        start_message = {
            "type": "session_start",
            "session_id": self.session_id
        }
        
        await websocket.send(json.dumps(start_message))
        logger.info(f"Started session: {self.session_id}")
        
        # Wait for session confirmation
        response = await websocket.recv()
        data = json.loads(response)
        logger.info(f"Session response: {data}")
    
    async def run_test_messages(self, websocket):
        """Send test messages and collect responses."""
        test_messages = [
            "What's the weather like today?",
            "I'm feeling really sad about my job.",
            "Why did the chicken cross the road?",
            "Can you help me with this math problem?",
            "I love pizza!",
            "My computer is broken again.",
            "What's 2+2?",
            "Tell me a joke!",
            "I'm having a terrible day.",
            "What do you think about artificial intelligence?",
            "I'm hungry.",
            "This code is driving me crazy!",
            "What's your favorite color?",
            "I just won the lottery!",
            "My car won't start."
        ]
        
        print(f"\n🧪 Testing {len(test_messages)} messages...")
        print("=" * 80)
        
        joke_responses = []
        
        for i, message in enumerate(test_messages, 1):
            print(f"\n📝 Test {i}: '{message}'")
            
            # Send message
            text_message = {
                "type": "text_message",
                "text": message,
                "session_id": self.session_id,
                "timestamp": time.time()
            }
            
            await websocket.send(json.dumps(text_message))
            
            # Wait for responses
            responses = await self.collect_responses(websocket, timeout=10)
            
            # Process responses
            joke_response = None
            for response in responses:
                if response.get("type") == "joke_response":
                    joke_response = response
                    break
            
            if joke_response:
                print(f"✅ Joke Response: {joke_response['joke_response']}")
                print(f"   Type: {joke_response['joke_type']}")
                print(f"   Confidence: {joke_response['confidence']:.2f}")
                
                joke_responses.append({
                    "input": message,
                    "joke": joke_response['joke_response'],
                    "type": joke_response['joke_type'],
                    "confidence": joke_response['confidence']
                })
            else:
                print("❌ No joke response generated")
                joke_responses.append({
                    "input": message,
                    "joke": None,
                    "type": "none",
                    "confidence": 0.0
                })
            
            print("-" * 60)
            
            # Small delay between messages
            await asyncio.sleep(0.5)
        
        # Summary
        self.print_summary(joke_responses)
        
        # End session
        await self.end_session(websocket)
    
    async def collect_responses(self, websocket, timeout: float = 5.0):
        """Collect all responses within the timeout period."""
        responses = []
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                # Wait for response with a short timeout
                response = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                data = json.loads(response)
                responses.append(data)
                
                # If we get a joke response, we can stop waiting
                if data.get("type") == "joke_response":
                    break
                    
            except asyncio.TimeoutError:
                # No more responses, break out
                break
            except Exception as e:
                logger.warning(f"Error receiving response: {e}")
                break
        
        return responses
    
    async def end_session(self, websocket):
        """End the WebSocket session."""
        end_message = {
            "type": "session_end",
            "session_id": self.session_id
        }
        
        await websocket.send(json.dumps(end_message))
        logger.info("Session ended")
    
    def print_summary(self, joke_responses: List[Dict]):
        """Print a summary of the test results."""
        print(f"\n📊 Test Summary")
        print("=" * 80)
        
        successful_jokes = sum(1 for r in joke_responses if r['joke'] is not None)
        total_tests = len(joke_responses)
        
        print(f"Total tests: {total_tests}")
        print(f"Successful jokes: {successful_jokes}")
        print(f"Success rate: {successful_jokes/total_tests*100:.1f}%")
        
        # Show joke types
        joke_types = {}
        for response in joke_responses:
            if response['joke']:
                joke_type = response['type']
                joke_types[joke_type] = joke_types.get(joke_type, 0) + 1
        
        if joke_types:
            print(f"\n🎭 Joke Types Generated:")
            for joke_type, count in joke_types.items():
                print(f"   {joke_type}: {count}")
        
        # Show some example jokes
        print(f"\n🎪 Example Jokes:")
        joke_examples = [r for r in joke_responses if r['joke']]
        for i, example in enumerate(joke_examples[:5], 1):  # Show first 5
            print(f"   {i}. Input: '{example['input']}'")
            print(f"      Joke: {example['joke']}")
            print(f"      Type: {example['type']}, Confidence: {example['confidence']:.2f}")
            print()

async def main():
    """Main function to run the WebSocket joke tester."""
    print("🎭 WebSocket Joke Responder Tester")
    print("=" * 50)
    print("This script will connect to your WebSocket server and test joke responses.")
    print("Make sure your server is running with: python main.py")
    print()
    
    # Check if server is likely running
    import socket
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(('localhost', 8000))
        sock.close()
        if result != 0:
            print("⚠️  Warning: Server doesn't appear to be running on localhost:8000")
            print("   Start your server first with: python main.py")
            print()
    except:
        pass
    
    tester = WebSocketJokeTester()
    await tester.connect_and_test()

if __name__ == "__main__":
    asyncio.run(main())
