# Joke Responder Integration

This document explains the new joke responder functionality that has been added to the backend.

## Overview

The joke responder listens to WebSocket messages (both audio transcriptions and text messages) and uses Groq's AI models to determine whether to respond with jokes or funny quips. It analyzes the context and appropriateness of the input text before generating humorous responses.

## Files Added/Modified

### New Files
- `joke_responder.py` - Main joke responder class with Groq integration
- `test_joke_responder.py` - Test script for the joke responder functionality
- `JOKE_RESPONDER_README.md` - This documentation file

### Modified Files
- `main.py` - Added joke responder integration to WebSocket endpoints
- `requirements.txt` - Added `groq` dependency

## Setup

1. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set Environment Variable**
   You need a Groq API key to use the joke responder:
   ```bash
   # Windows
   set GROQ_API_KEY=your_groq_api_key_here
   
   # Linux/Mac
   export GROQ_API_KEY=your_groq_api_key_here
   ```

3. **Get Groq API Key**
   - Visit [https://console.groq.com/](https://console.groq.com/)
   - Sign up for an account
   - Generate an API key from the dashboard

## Usage

### WebSocket Endpoints

The joke responder is integrated into two WebSocket endpoints:

1. **Audio WebSocket** (`/ws/audio`)
   - Processes audio transcriptions
   - Automatically analyzes transcribed text for joke opportunities
   - Sends joke responses when appropriate

2. **Text WebSocket** (`/ws/text`)
   - Processes direct text messages
   - Useful for testing and direct text-based interactions

### WebSocket Message Format

#### Sending Messages
```json
{
  "type": "text_message",
  "text": "Your message here",
  "session_id": "optional_session_id",
  "timestamp": "optional_timestamp"
}
```

#### Receiving Joke Responses
```json
{
  "type": "joke_response",
  "session_id": "session_id",
  "original_text": "Original input text",
  "joke_response": "Generated joke or quip",
  "joke_type": "pun|observational|wordplay|situational",
  "confidence": 0.85,
  "timestamp": "timestamp"
}
```

## Configuration

The joke responder can be configured by modifying the `JokeResponder` class:

- `joke_threshold` (default: 0.7) - Minimum confidence required to generate a joke
- `max_response_length` (default: 200) - Maximum length of joke responses
- `model` (default: "llama-3.1-70b-versatile") - Groq model to use

## Testing

Run the test script to verify everything is working:

```bash
python test_joke_responder.py
```

The test script will:
- Check if the Groq API key is set
- Test various input texts
- Show joke generation results
- Display success rates and joke type distributions

## Example Usage

### Starting the Server
```bash
python main.py
```

### Connecting to Text WebSocket
```javascript
const ws = new WebSocket('ws://localhost:8000/ws/text');

// Start session
ws.send(JSON.stringify({
  type: 'session_start',
  session_id: 'my_session'
}));

// Send text message
ws.send(JSON.stringify({
  type: 'text_message',
  text: 'I love pizza!',
  session_id: 'my_session'
}));

// Listen for responses
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  if (data.type === 'joke_response') {
    console.log('Joke:', data.joke_response);
  }
};
```

## How It Works

1. **Text Analysis**: The system analyzes incoming text to determine if it's appropriate for a joke response
2. **Context Evaluation**: Considers factors like:
   - Is the text asking a question?
   - Is the context appropriate for humor?
   - Would a joke add value to the conversation?
   - Is the text too serious or sensitive?
3. **Joke Generation**: If appropriate, generates a relevant joke or quip using Groq's AI
4. **Response Delivery**: Sends the joke response back through the WebSocket

## Joke Types

The system can generate different types of jokes:
- **Pun**: Wordplay and puns
- **Observational**: Observations about everyday life
- **Wordplay**: Clever use of language
- **Situational**: Context-specific humor
- **General**: General funny responses

## Error Handling

The system includes comprehensive error handling:
- Graceful fallback if Groq API is unavailable
- Logging of all errors and warnings
- Non-blocking operation (joke generation won't break the main functionality)
- Confidence scoring to avoid inappropriate responses

## Performance Considerations

- Joke generation is asynchronous and won't block other operations
- Responses are cached briefly to avoid duplicate processing
- The system uses efficient API calls to minimize latency
- Confidence thresholds prevent over-generating jokes

## Troubleshooting

### Common Issues

1. **"Groq API key is required" error**
   - Make sure you've set the `GROQ_API_KEY` environment variable
   - Verify the API key is valid and has sufficient credits

2. **No joke responses generated**
   - Check the confidence threshold settings
   - Some texts may not be appropriate for jokes
   - Review the logs for error messages

3. **Import errors**
   - Run `pip install -r requirements.txt` to install dependencies
   - Make sure you're using Python 3.7+

### Debug Mode

Enable debug logging to see more detailed information:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Future Enhancements

Potential improvements for the joke responder:
- Custom joke templates and styles
- User preference learning
- Multi-language support
- Joke rating and feedback system
- Integration with other AI models
- Customizable humor styles (sarcastic, witty, dad jokes, etc.)
