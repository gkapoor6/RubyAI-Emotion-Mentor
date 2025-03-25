import os
from anthropic import Anthropic
from typing import List, Dict, Any
import json
from datetime import datetime
import logging

def get_emotion_insights(emotion_data):
    """Generate insights from emotion data using Claude."""
    try:
        # Set up logging
        logging.basicConfig(level=logging.INFO)
        
        # Log the raw emotion data
        logging.info(f"Raw emotion data received: {json.dumps(emotion_data, indent=2)}")
        
        # Check if we have any emotion data
        if not emotion_data or len(emotion_data) == 0:
            logging.warning("No emotion data available")
            return {
                "error": "No emotion data available yet. Start tracking your emotions to receive insights.",
                "timestamp": datetime.now().strftime("%I:%M %p")
            }

        # Initialize Anthropic client
        api_key = os.getenv('ANTHROPIC_API_KEY')
        if not api_key:
            logging.error("Anthropic API key not configured")
            return {
                "error": "Anthropic API key not configured.",
                "timestamp": datetime.now().strftime("%I:%M %p")
            }
            
        logging.info("API key found, initializing Anthropic client")
        anthropic = Anthropic(api_key=api_key)
        
        # Format the request to Claude
        prompt = f"""Based on the following emotional data, provide a brief analysis focusing on the most specific and actionable insights. 
        Keep insights to 1-2 sentences and avoid generic advice. Focus on patterns that are unique to this emotional journey.

        Emotional Data:
        {json.dumps(emotion_data, indent=2)}

        Please provide:
        1. A 1-2 sentence summary of the most significant emotional patterns
        2. A single, highly specific actionable insight (not generic advice)
        3. A thought-provoking journaling prompt that relates to the specific emotions observed

        Format the response as JSON with keys: summary, insight, and prompt."""

        # Log the formatted prompt being sent to Claude
        logging.info(f"Sending prompt to Claude:\n{prompt}")

        try:
            # Get response from Claude
            response = anthropic.messages.create(
                model="claude-3-sonnet",
                max_tokens=500,
                temperature=0.7,
                system="You are an expert in emotional intelligence and personal growth. Provide specific, actionable insights based on emotional patterns.",
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )
            
            # Parse the response
            response_text = response.content[0].text
            logging.info(f"Received response from Claude:\n{response_text}")
            
            # Validate JSON response
            try:
                insights = json.loads(response_text)
                if not all(key in insights for key in ["summary", "insight", "prompt"]):
                    raise ValueError("Missing required keys in response")
                
                # Add timestamp
                result = {
                    "timestamp": datetime.now().strftime("%I:%M %p"),
                    "insights": response_text
                }
                
                return result
            except json.JSONDecodeError as e:
                logging.error(f"Invalid JSON response from Claude: {str(e)}")
                raise
            
        except Exception as e:
            logging.error(f"Error calling Claude API: {str(e)}")
            raise
        
    except Exception as e:
        logging.error(f"Error generating insights: {str(e)}", exc_info=True)
        return {
            "error": "Unable to generate insights at this time.",
            "timestamp": datetime.now().strftime("%I:%M %p")
        } 