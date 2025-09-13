#!/usr/bin/env python3
"""
Setup and test script for the joke responder system.
This script will help you set up the environment and test the system.
"""

import os
import sys
import subprocess
import asyncio
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def check_python_version():
    """Check if Python version is compatible."""
    if sys.version_info < (3, 7):
        print("❌ Error: Python 3.7 or higher is required.")
        print(f"   Current version: {sys.version}")
        return False
    print(f"✅ Python version: {sys.version.split()[0]}")
    return True

def check_groq_api_key():
    """Check if Groq API key is set."""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        print("❌ Error: GROQ_API_KEY environment variable is not set.")
        print("\nTo set your Groq API key:")
        print("  Windows: set GROQ_API_KEY=your_api_key_here")
        print("  Linux/Mac: export GROQ_API_KEY=your_api_key_here")
        print("\nGet your API key from: https://console.groq.com/")
        return False
    print("✅ GROQ_API_KEY is set")
    return True

def install_dependencies():
    """Install required dependencies."""
    print("\n📦 Installing dependencies...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("✅ Dependencies installed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install dependencies: {e}")
        return False

async def test_joke_responder():
    """Test the joke responder functionality."""
    print("\n🧪 Testing joke responder...")
    try:
        from joke_responder import JokeResponder
        
        responder = JokeResponder()
        
        # Test with a simple statement
        test_text = "I love pizza!"
        print(f"Testing with: '{test_text}'")
        
        result = await responder.process_text_for_joke(test_text)
        
        if result:
            print(f"✅ Joke generated: {result['joke_response']}")
            print(f"   Type: {result['joke_type']}")
            print(f"   Confidence: {result['confidence']:.2f}")
            return True
        else:
            print("❌ No joke generated")
            return False
            
    except Exception as e:
        print(f"❌ Joke responder test failed: {e}")
        return False

def main():
    """Main setup and test function."""
    print("🎭 Joke Responder Setup and Test")
    print("=" * 50)
    
    # Check Python version
    if not check_python_version():
        return False
    
    # Check Groq API key
    if not check_groq_api_key():
        return False
    
    # Install dependencies
    if not install_dependencies():
        return False
    
    # Test joke responder
    try:
        result = asyncio.run(test_joke_responder())
        if result:
            print("\n🎉 Setup completed successfully!")
            print("\nNext steps:")
            print("1. Run the server: python main.py")
            print("2. Test with WebSocket: python test_websocket_jokes.py")
            print("3. Test directly: python simple_joke_test.py")
            return True
        else:
            print("\n⚠️  Setup completed but joke responder test failed.")
            return False
    except Exception as e:
        print(f"\n❌ Setup failed: {e}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
