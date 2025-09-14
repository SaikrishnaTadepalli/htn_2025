import base64
import logging
import os
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
            img_bytes = base64.b64decode(frame_data)

            # Create Vision API image object
            image = vision.Image(content=img_bytes)

            # Perform face detection with emotion analysis
            response = self.client.face_detection(image=image)
            faces = response.face_annotations

            if response.error.message:
                return {'success': False, 'error': f'Vision API error: {response.error.message}'}

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