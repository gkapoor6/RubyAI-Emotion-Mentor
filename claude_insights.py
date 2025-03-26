import os
from anthropic import Anthropic, APIError, APITimeoutError, APIConnectionError
from typing import List, Dict, Any, Optional, Tuple
import json
from datetime import datetime
import logging
import time
import backoff  # You'll need to pip install backoff
from tenacity import retry, stop_after_attempt, wait_exponential  # You'll need to pip install tenacity

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class JSONExtractionError(Exception):
    """Custom exception for JSON extraction failures"""
    pass

class InsightsGenerationError(Exception):
    """Custom exception for insights generation failures"""
    pass

def extract_json_with_fallbacks(text: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Attempts multiple methods to extract valid JSON from text.
    Returns (json_str, method_used) or (None, error_message)
    """
    methods = [
        ('code_block', lambda t: t.split('```json')[1].split('```')[0].strip() if '```json' in t else None),
        ('markdown_block', lambda t: t.split('```')[1].split('```')[0].strip() if '```' in t else None),
        ('curly_braces', lambda t: t[t.find('{'):t.rfind('}')+1] if '{' in t and '}' in t else None),
        ('first_line', lambda t: t.split('\n')[0].strip()),
        ('last_line', lambda t: t.split('\n')[-1].strip())
    ]
    
    errors = []
    for method_name, extractor in methods:
        try:
            extracted = extractor(text)
            if extracted:
                # Try to parse as JSON to validate
                json.loads(extracted)
                return extracted, method_name
        except Exception as e:
            errors.append(f"{method_name}: {str(e)}")
            continue
    
    return None, f"All extraction methods failed: {'; '.join(errors)}"

def validate_insights_format(data: Dict) -> Tuple[bool, Optional[str]]:
    """Validate the structure and content of insights data"""
    try:
        required_keys = ["summary", "insight", "prompt"]
        
        # Check for required keys
        if not all(key in data for key in required_keys):
            missing = [key for key in required_keys if key not in data]
            return False, f"Missing required keys: {missing}"
            
        # Check for non-empty string values
        for key in required_keys:
            if not isinstance(data[key], str) or not data[key].strip():
                return False, f"Empty or invalid value for key: {key}"
                
        return True, None
        
    except Exception as e:
        return False, f"Validation error: {str(e)}"

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    retry_error_callback=lambda retry_state: None  # Return None on final failure
)
def call_claude_with_retries(anthropic: Anthropic, model: str, prompt: str, max_retries: int = 3) -> Optional[Dict]:
    """Make API call to Claude with retries and error handling"""
    try:
        response = anthropic.messages.create(
            model=model,
            max_tokens=500,
            temperature=0.7,
            system="You are an expert in emotional intelligence and personal growth. Your responses must be valid JSON objects with exactly these three keys: summary, insight, and prompt. Wrap your response in ```json code blocks.",
            messages=[{"role": "user", "content": prompt}]
        )
        return response
    except (APIError, APITimeoutError, APIConnectionError) as e:
        logger.error(f"Claude API error with model {model}: {str(e)}")
        raise  # Let retry handle it
    except Exception as e:
        logger.error(f"Unexpected error calling Claude API: {str(e)}")
        return None

def get_emotion_insights(emotion_data: List[Dict]) -> Dict:
    """Generate insights from emotion data using Claude with enhanced resilience"""
    try:
        # Input validation
        if not emotion_data or not isinstance(emotion_data, list):
            return {
                "error": "No emotion data available yet. Start tracking your emotions to receive insights.",
                "timestamp": datetime.now().strftime("%I:%M %p")
            }

        # API key validation
        api_key = os.getenv('ANTHROPIC_API_KEY')
        if not api_key:
            return {
                "error": "Anthropic API key not configured.",
                "timestamp": datetime.now().strftime("%I:%M %p")
            }
            
        logger.info("Initializing Anthropic client")
        anthropic = Anthropic(api_key=api_key)
        
        # Format the request
        prompt = """Based on the following emotional data, provide a brief analysis. Here's how our data is collected and processed:

        1. Audio Collection: We record short audio snippets throughout the day
        2. Processing Windows: We group these recordings into 20-minute intervals
        3. Sampling Method: For each 20-minute interval, we randomly select up to 5 audio files to analyze
        4. Intensity Selection: From these 5 files, we select the emotions with the highest intensity to represent that time period
        
        This means that:
        - Each data point represents the strongest emotions detected within a 20-minute window
        - Not all audio snippets are analyzed (we sample 5 per interval)
        - Gaps between data points are normal and expected
        - Sudden changes between intervals can occur due to our sampling method

        Given this context, please analyze this emotional data:
        """ + json.dumps(emotion_data, indent=2) + """

        Please provide:
        1. A 1-2 sentence summary of the most significant emotional patterns, considering our sampling methodology
        2. A single, highly specific actionable insight that acknowledges both the natural ebb and flow of emotions and our data collection method
        3. A thought-provoking journaling prompt that helps reflect on the emotional patterns while understanding these are sampled snapshots

        Your response MUST be a valid JSON object with exactly these three keys: summary, insight, and prompt.
        Wrap your response in ```json code blocks like this:
        ```json
        {
            "summary": "Your summary here",
            "insight": "Your insight here",
            "prompt": "Your prompt here"
        }
        ```"""

        # Try different Claude models with retries
        models_to_try = [
            "claude-3-opus-20240229",
            "claude-3-sonnet-20240229",
            "claude-3-haiku-20240307",
            "claude-2.1",
            "claude-2.0"
        ]
        
        response = None
        last_error = None
        
        for model in models_to_try:
            try:
                logger.info(f"Attempting to use model: {model}")
                response = call_claude_with_retries(anthropic, model, prompt)
                if response:
                    logger.info(f"Successfully used model: {model}")
                    break
            except Exception as e:
                last_error = str(e)
                logger.warning(f"Failed to use model {model}: {last_error}")
                continue
        
        if not response:
            raise InsightsGenerationError(f"All Claude models failed. Last error: {last_error}")
        
        # Extract and validate JSON from response
        response_text = response.content[0].text
        logger.info(f"Raw response from Claude:\n{response_text}")
        
        json_str, method = extract_json_with_fallbacks(response_text)
        if not json_str:
            raise JSONExtractionError(f"Failed to extract JSON: {method}")
            
        try:
            insights = json.loads(json_str)
        except json.JSONDecodeError as e:
            raise JSONExtractionError(f"Invalid JSON format: {str(e)}")
        
        # Validate insights format
        is_valid, error_msg = validate_insights_format(insights)
        if not is_valid:
            raise InsightsGenerationError(f"Invalid insights format: {error_msg}")
        
        # Success! Return the insights with timestamp
        return {
            "timestamp": datetime.now().strftime("%I:%M %p"),
            "insights": insights
        }
        
    except (JSONExtractionError, InsightsGenerationError) as e:
        logger.error(str(e))
        return {
            "error": str(e),
            "timestamp": datetime.now().strftime("%I:%M %p")
        }
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        return {
            "error": "An unexpected error occurred while generating insights.",
            "timestamp": datetime.now().strftime("%I:%M %p")
        } 