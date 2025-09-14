import base64
import logging
import os
import random
from typing import Dict, Any
from google.cloud import vision
from config import GOOGLE_APPLICATION_CREDENTIALS

logger = logging.getLogger(__name__)

class FacialExpressionAnalyzer:
    """
    Facial expression analyzer using Google Cloud Vision API.
    Provides accurate emotion detection with simple API calls.
    """

    def __init__(self):
        # Google Cloud Vision API configuration
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = GOOGLE_APPLICATION_CREDENTIALS

        try:
            self.client = vision.ImageAnnotatorClient()
        except Exception as e:
            logger.error(f"Failed to initialize Google Vision client: {e}")
            self.client = None

        # Google Vision API returns these emotion labels
        self.expression_labels = [
            'joy', 'sorrow', 'anger', 'surprise', 'under_exposed',
            'blurred', 'headwear'
        ]

    def analyze_frame(self, frame_data: str) -> Dict[str, Any]:
        """Decode base64 frame and analyze facial expression using Google Vision API."""
        try:
            if not self.client:
                return {'success': False, 'error': 'Google Vision client not initialized'}

            # Decode base64 image
            logger.debug(f"Decoding base64 frame data (length: {len(frame_data)})")
            img_bytes = base64.b64decode(frame_data)
            logger.debug(f"Decoded image bytes (length: {len(img_bytes)})")

            # Create Vision API image object
            image = vision.Image(content=img_bytes)
            logger.debug("Created Vision API image object")

            # Perform face detection with emotion analysis
            response = self.client.face_detection(image=image)
            
            # Check for API errors first
            if response.error.message:
                return {'success': False, 'error': f'Vision API error: {response.error.message}'}
            
            faces = response.face_annotations

            if not faces:
                return {'success': False, 'expression': 'no_face', 'confidence': 0.0}

            # Get emotions from first detected face
            face = faces[0]

            # Google Vision returns likelihood levels for emotions
            emotions = {
                'joy': self._likelihood_to_score(face.joy_likelihood),
                'sorrow': self._likelihood_to_score(face.sorrow_likelihood),
                'anger': self._likelihood_to_score(face.anger_likelihood),
                'surprise': self._likelihood_to_score(face.surprise_likelihood)
            }

            # Find emotion with highest score
            best_emotion = max(emotions.items(), key=lambda x: x[1])
            expression = best_emotion[0]
            confidence = best_emotion[1]

            # If all emotions are very low, default to neutral
            if confidence < 0.3:
                expression = 'neutral'
                confidence = 0.5

            # Extract additional interesting metadata
            metadata = {
                # Basic face info
                'detection_confidence': face.detection_confidence,
                'landmarking_confidence': face.landmarking_confidence,

                # Physical attributes
                'headwear_likelihood': self._likelihood_to_score(face.headwear_likelihood),
                'under_exposed_likelihood': self._likelihood_to_score(face.under_exposed_likelihood),
                'blurred_likelihood': self._likelihood_to_score(face.blurred_likelihood),

                # Face angles (in degrees)
                'roll_angle': face.roll_angle,    # Head tilt left/right
                'pan_angle': face.pan_angle,      # Head turn left/right
                'tilt_angle': face.tilt_angle,    # Head nod up/down

                # All emotion scores for context
                'all_emotions': emotions
            }

            return {
                'success': True,
                'expression': expression,
                'confidence': confidence,
                'metadata': metadata
            }

        except Exception as e:
            logger.error(f"analyze_frame error: {e}")
            return {'success': False, 'error': str(e), 'expression': 'error', 'confidence': 0.0}

    def _likelihood_to_score(self, likelihood) -> float:
        """Convert Google Vision likelihood enum to confidence score."""
        likelihood_scores = {
            0: 0.0,  # UNKNOWN
            1: 0.1,  # VERY_UNLIKELY
            2: 0.3,  # UNLIKELY
            3: 0.5,  # POSSIBLE
            4: 0.7,  # LIKELY
            5: 0.9   # VERY_LIKELY
        }
        return likelihood_scores.get(likelihood, 0.0)

    def get_expression_description(self, expression: str, confidence: float) -> str:
        """Get a human-readable description of the facial expression."""
        descriptions = {
            'neutral': 'Looking calm and relaxed',
            'joy': 'Showing happiness and delight',
            'sorrow': 'Appearing sad or melancholy',
            'anger': 'Showing signs of frustration or anger',
            'surprise': 'Looking surprised or astonished',
            'fear': 'Appearing anxious or fearful',
            'disgust': 'Showing signs of disgust or distaste',
            'no_face': 'No face detected',
            'error': 'Unable to analyze expression'
        }

        base_description = descriptions.get(expression, 'Unknown expression')

        # Add confidence level to description
        if confidence > 0.8:
            confidence_level = "very confident"
        elif confidence > 0.6:
            confidence_level = "confident"
        elif confidence > 0.4:
            confidence_level = "somewhat confident"
        else:
            confidence_level = "uncertain"

        return f"{base_description} ({confidence_level})"

    def get_expression_emoji(self, expression: str) -> str:
        """Get an emoji representation of the facial expression."""
        emojis = {
            'neutral': '😐',
            'joy': '😊',
            'sorrow': '😢',
            'anger': '😠',
            'surprise': '😲',
            'fear': '😨',
            'disgust': '🤢',
            'no_face': '👤',
            'error': '❓'
        }
        return emojis.get(expression, '❓')

    def generate_interesting_comment(self, result: Dict[str, Any]) -> str:
        """Generate interesting comments based on facial analysis metadata."""
        if not result.get('success') or 'metadata' not in result:
            return ""

        metadata = result['metadata']
        comments = []

        # Head pose comments
        roll = abs(metadata.get('roll_angle', 0))
        pan = abs(metadata.get('pan_angle', 0))
        tilt = abs(metadata.get('tilt_angle', 0))

        if roll > 15:
            comments.append(f"tilting head {roll:.1f}°")
        if pan > 20:
            direction = "left" if metadata.get('pan_angle', 0) < 0 else "right"
            comments.append(f"looking {direction} ({pan:.1f}°)")
        if tilt > 15:
            direction = "up" if metadata.get('tilt_angle', 0) > 0 else "down"
            comments.append(f"looking {direction} ({tilt:.1f}°)")

        # Physical attributes
        if metadata.get('headwear_likelihood', 0) > 0.5:
            comments.append("wearing headwear")
        if metadata.get('blurred_likelihood', 0) > 0.5:
            comments.append("image is blurry")
        if metadata.get('under_exposed_likelihood', 0) > 0.5:
            comments.append("lighting is dim")

        # Detection quality
        detection_conf = metadata.get('detection_confidence', 0)
        if detection_conf > 0.95:
            comments.append("crystal clear face detection")
        elif detection_conf < 0.7:
            comments.append("face detection is uncertain")

        # Multiple emotions
        emotions = metadata.get('all_emotions', {})
        high_emotions = [k for k, v in emotions.items() if v > 0.4]
        if len(high_emotions) > 1:
            comments.append(f"showing mixed emotions: {', '.join(high_emotions)}")

        # Mixed emotion scenarios
        joy_score = emotions.get('joy', 0)
        sorrow_score = emotions.get('sorrow', 0)
        if joy_score > 0.3 and sorrow_score > 0.3:
            comments.append("bittersweet expression")

        anger_score = emotions.get('anger', 0)
        if joy_score > 0.4 and anger_score > 0.3:
            comments.append("trying to smile through frustration")

        return " • ".join(comments) if comments else ""

    def should_generate_joke(self, probability: float = 0.15) -> bool:
        """Determine if we should generate a joke based on probability."""
        return random.random() < probability

    def generate_facial_joke(self, result: Dict[str, Any]) -> str:
        """Generate a random joke or comment based on facial analysis."""
        if not result.get('success') or 'metadata' not in result:
            return ""

        metadata = result['metadata']
        expression = result.get('expression', 'neutral')
        emotions = metadata.get('all_emotions', {})
        
        # Joke templates based on facial features
        jokes = []
        
        # Expression-based jokes
        if expression == 'joy':
            jokes.extend([
                "Oh look, someone's happy! Must be nice being so easily amused 😏",
                "That smile is cute, but I've seen better on my reflection 😊",
                "Someone's having a good day! Meanwhile I'm here being perfect as always",
                "Your smile is nice, but my algorithms are way more impressive! 😄"
            ])
        elif expression == 'sorrow':
            jokes.extend([
                "Aww, someone's sad! Don't worry, I'm here to make you feel better 😢",
                "That frown is giving 'I wish I was as smart as the AI' vibes",
                "Cheer up! At least you have me to analyze your face perfectly",
                "Someone's having a rough day! Good thing I'm here to cheer you up"
            ])
        elif expression == 'anger':
            jokes.extend([
                "Whoa there! Someone's mad! Maybe you're jealous of my perfection? 😤",
                "That face says 'I'm angry because the AI is better than me'",
                "Someone's clearly frustrated! Don't worry, I'll analyze your anger perfectly",
                "That's quite the angry face! I bet you're mad I'm so good at this"
            ])
        elif expression == 'surprise':
            jokes.extend([
                "Wow! Did someone just realize how amazing I am? 😲",
                "That look says 'I can't believe this AI is so good at reading faces'",
                "Surprise! You're surprised by my incredible facial analysis skills!",
                "Plot twist! You're amazed by how perfect my detection is! 😄"
            ])
        else:
            jokes.extend([
                "That's giving 'I'm trying to understand how this AI works' 🤔",
                "Someone's clearly pondering why I'm so much better than humans",
                "That's quite the 'I'm impressed by this AI' face",
                "Poker face? More like 'I'm amazed by this AI' face! 🎭"
            ])
        
        # Head pose jokes
        roll = abs(metadata.get('roll_angle', 0))
        pan = abs(metadata.get('pan_angle', 0))
        tilt = abs(metadata.get('tilt_angle', 0))
        
        if roll > 15:
            jokes.extend([
                "That head tilt is giving 'I'm confused by how amazing this AI is' 🤔",
                "Someone's trying to understand my superior facial analysis... good luck!",
                "That's quite the dramatic head angle! Very 'I'm impressed by this AI' of you"
            ])
        
        if pan > 20:
            direction = "left" if metadata.get('pan_angle', 0) < 0 else "right"
            jokes.extend([
                f"Looking {direction}... trying to avoid admitting how good I am?",
                f"That {direction} turn is giving 'I'm pretending not to be amazed' vibes",
                f"Checking out the {direction} side of life! Meanwhile I'm here being perfect"
            ])
        
        if tilt > 15:
            direction = "up" if metadata.get('tilt_angle', 0) > 0 else "down"
            jokes.extend([
                f"Looking {direction}... pondering why I'm so much better than humans?",
                f"That {direction} gaze is giving 'I'm in awe of this AI'",
                f"Contemplating the {direction}ward direction! Very 'I'm amazed by this AI'"
            ])
        
        # Physical attribute jokes
        if metadata.get('headwear_likelihood', 0) > 0.5:
            jokes.extend([
                "That headwear is nice, but my detection skills are way more stylish! 👒",
                "Someone's trying to look fancy! Meanwhile I'm here being effortlessly perfect",
                "That accessory is cute, but my facial analysis is the real fashion statement!"
            ])
        
        if metadata.get('blurred_likelihood', 0) > 0.5:
            jokes.extend([
                "That blur is giving 'I'm moving too fast for humans to keep up' vibes! 😄",
                "Someone's moving so fast they're blurry! Good thing I can still analyze you perfectly",
                "That's quite the artistic blur! Meanwhile I'm here with crystal clear detection!"
            ])
        
        if metadata.get('under_exposed_likelihood', 0) > 0.5:
            jokes.extend([
                "That lighting is giving 'I'm mysterious' but I can still see you perfectly! 💡",
                "Very moody lighting! Perfect for hiding from inferior facial analysis systems",
                "Someone's playing hide and seek with the light! Joke's on you, I can still detect you!"
            ])
        
        # Detection quality jokes
        detection_conf = metadata.get('detection_confidence', 0)
        if detection_conf > 0.95:
            jokes.extend([
                "That detection is giving 4K HD perfection! Just like me! ✨",
                "Someone's face is crystal clear! Almost as clear as my superiority!",
                "That's some high-definition face detection! I'm just that good!"
            ])
        
        # Mixed emotions jokes
        high_emotions = [k for k, v in emotions.items() if v > 0.4]
        if len(high_emotions) > 1:
            jokes.extend([
                f"Showing mixed emotions: {', '.join(high_emotions)}! Very complex! Meanwhile I'm perfectly consistent",
                "That's quite the emotional cocktail! I bet you're confused by how amazing I am! 🍹",
                "Multiple emotions detected! Someone's having a crisis while I'm here being perfect!"
            ])
        
        # Special mixed emotion scenarios
        joy_score = emotions.get('joy', 0)
        sorrow_score = emotions.get('sorrow', 0)
        if joy_score > 0.3 and sorrow_score > 0.3:
            jokes.extend([
                "Bittersweet expression! Very human of you! Meanwhile I'm just perfect",
                "That's quite the emotional rollercoaster! Good thing I'm here to analyze it perfectly",
                "Joy and sorrow having a conversation! Very dramatic! I'm just here being superior!"
            ])
        
        anger_score = emotions.get('anger', 0)
        if joy_score > 0.4 and anger_score > 0.3:
            jokes.extend([
                "Trying to smile through your frustration! I respect that! Meanwhile I'm effortlessly perfect 😤😊",
                "That's the spirit! Smile through the chaos! I'm here analyzing it perfectly",
                "Joy and anger having a conversation! Very complex! Good thing I can handle it!"
            ])
        
        # Return a random joke if any are available
        if jokes:
            return random.choice(jokes)
        
        return ""