import os
from anthropic import Anthropic, APIError, APITimeoutError, APIConnectionError
from typing import List, Dict, Any, Optional, Tuple
import json
from datetime import datetime
import logging
import time
import backoff  # You'll need to pip install backoff
from tenacity import retry, stop_after_attempt, wait_exponential  # You'll need to pip install tenacity
from dotenv import load_dotenv
import anthropic

# Load environment variables
load_dotenv()

# Initialize Anthropic client
client = anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))

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

def get_latest_sonnet_model() -> str:
    """
    Fetch the latest available Claude 3 Sonnet model name.
    Falls back to a default if API call fails.
    """
    try:
        # Get available models
        models = client.models.list()
        
        # Log all available models for debugging
        logger.info("Available models:")
        for model in models:
            logger.info(f"- {model.id}")
        
        # Filter for Claude 3 Sonnet models and sort by creation date
        sonnet_models = [
            model for model in models 
            if 'claude-3' in model.id.lower() and 'sonnet' in model.id.lower()
        ]
        
        if sonnet_models:
            # Sort by creation date (newest first) and get the latest
            latest_model = sorted(
                sonnet_models,
                key=lambda x: x.created_at,
                reverse=True
            )[0]
            logger.info(f"Using Claude model: {latest_model.id}")
            return latest_model.id
        else:
            # Try alternative model names in order of preference
            alternative_models = [
                "claude-3-7-sonnet-20250219",
                "claude-3-5-sonnet-20241022",
                "claude-3-5-sonnet-20240620",
                "claude-3-haiku-20240307",
                "claude-3-opus-20240229"
            ]
            
            for model_name in alternative_models:
                if any(model_name in model.id.lower() for model in models):
                    logger.info(f"Using alternative model: {model_name}")
                    return model_name
            
            logger.warning("No suitable Claude models found, using default")
            return "claude-3-7-sonnet-20250219"  # Most recent model
            
    except Exception as e:
        logger.error(f"Error fetching models: {str(e)}")
        # Fallback to most recent model
        return "claude-3-7-sonnet-20250219"

def get_emotion_insights(emotion_data):
    """
    Generate insights about emotions using Claude.
    emotion_data is a list of dicts with 'timestamp' and 'emotions' keys.
    """
    try:
        # Format the emotion data for the prompt
        emotion_text = ""
        for entry in emotion_data:
            emotion_text += f"\n{entry['timestamp']}:\n"
            for emotion in entry['emotions']:
                intensity = round(emotion['score'] * 100, 1)
                emotion_text += f"- {emotion['name']}: {intensity}%\n"

        prompt = f"""You are an expert emotional intelligence analyst. Analyze the following emotion data and provide insights that are personal, empathetic, and actionable. Focus on the emotional journey and patterns, without mentioning any technical aspects of data collection or processing.

Emotion Data:
{emotion_text}

Provide three separate paragraphs, each with exactly two sentences. Use [SECTION] markers to separate them:

[SUMMARY]
Two sentences describing the overall emotional journey and key transitions.

[INSIGHTS]
Two sentences explaining the most significant patterns and their meaning.

[PROMPT]
First sentence: A reflection question.
Second sentence: An action step.

Be concise and impactful with each sentence. Keep the tone warm and supportive, focusing on emotional awareness and growth."""

        # Get the latest available model
        model_name = get_latest_sonnet_model()
        logger.info(f"Attempting to use model: {model_name}")
        
        try:
            message = client.messages.create(
                model=model_name,
                max_tokens=1000,
                temperature=0.7,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )
            # Log Claude's response
            logger.info("Claude's response:")
            logger.info(message.content[0].text)

            # Parse response using section markers
            response = message.content[0].text
            sections = {}
            
            # Extract each section using markers
            for section in ['SUMMARY', 'INSIGHTS', 'PROMPT']:
                try:
                    section_text = response.split(f'[{section}]')[1].split('[')[0].strip()
                    sections[section.lower()] = section_text
                except IndexError:
                    logger.error(f"Could not find section: {section}")
                    sections[section.lower()] = f"Unable to generate {section.lower()}."

            return {
                "summary": sections.get('summary', "Unable to generate summary."),
                "insight": sections.get('insights', "Unable to generate insights."),
                "prompt": sections.get('prompt', "Unable to generate journal prompt.")
            }

        except Exception as e:
            logger.error(f"Error with model {model_name}: {str(e)}")
            # Try fallback model with same logic...
            fallback_model = "claude-3-7-sonnet-20250219"
            logger.info(f"Trying fallback model: {fallback_model}")
            message = client.messages.create(
                model=fallback_model,
                max_tokens=1000,
                temperature=0.7,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )
            # Log Claude's response for fallback model
            logger.info("Claude's response (fallback model):")
            logger.info(message.content[0].text)

            # Parse response using section markers (same logic as above)
            response = message.content[0].text
            sections = {}
            
            for section in ['SUMMARY', 'INSIGHTS', 'PROMPT']:
                try:
                    section_text = response.split(f'[{section}]')[1].split('[')[0].strip()
                    sections[section.lower()] = section_text
                except IndexError:
                    logger.error(f"Could not find section: {section}")
                    sections[section.lower()] = f"Unable to generate {section.lower()}."

            return {
                "summary": sections.get('summary', "Unable to generate summary."),
                "insight": sections.get('insights', "Unable to generate insights."),
                "prompt": sections.get('prompt', "Unable to generate journal prompt.")
            }

    except Exception as e:
        logger.error(f"Error generating insights: {str(e)}")
        return {
            "summary": "Unable to analyze emotions at this time.",
            "insight": "Please try again later.",
            "prompt": "Take a moment to reflect on your current emotional state."
        } 