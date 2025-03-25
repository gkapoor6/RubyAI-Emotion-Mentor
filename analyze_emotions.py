"""
This script uses the Hume AI SDK's streaming API to analyze emotions in audio files.
Based on the official Hume AI SDK streaming example.

Note: The speech prosody model analyzes tune, rhythm, and timbre of speech in audio files (.mp3 and .wav supported).
Each audio file should be 5 seconds or less in duration.
"""

import asyncio
import os
import json
import ssl
import certifi
import tempfile
from datetime import datetime
from dotenv import load_dotenv
from hume import AsyncHumeClient
from hume.expression_measurement.stream import Config
from hume.expression_measurement.stream.socket_client import StreamConnectOptions
from websockets.client import connect
import sys

# Create an SSL context using certifi's certificates
ssl_context = ssl.create_default_context(cafile=certifi.where())

def serialize_predictions(obj):
    """Helper function to serialize prediction objects."""
    if hasattr(obj, 'dict'):
        return obj.dict()
    elif hasattr(obj, '__dict__'):
        return obj.__dict__
    else:
        return str(obj)

def trim_audio(filepath):
    """Trim audio file to 5 seconds if longer and normalize the audio."""
    temp_dir = tempfile.mkdtemp()
    base_filename = os.path.basename(filepath)
    trimmed_filepath = os.path.join(temp_dir, f"trimmed_{base_filename}")
    normalized_filepath = os.path.join(temp_dir, f"normalized_{base_filename}")
    
    # Use sox to trim the audio file
    os.system(f'sox "{filepath}" "{trimmed_filepath}" trim 0 5.0')
    
    # Normalize the audio (adjust volume to peak at -1 dB)
    os.system(f'sox "{trimmed_filepath}" "{normalized_filepath}" norm -1')
    
    # Clean up the intermediate file
    os.remove(trimmed_filepath)
    
    return normalized_filepath

async def process_audio_file(socket, filepath):
    """Process a single audio file and analyze emotions."""
    trimmed_filepath = None
    try:
        print(f"\nProcessing {os.path.basename(filepath)}...")
        
        # Trim audio file if needed
        trimmed_filepath = trim_audio(filepath)
        print(f"Trimmed to 5 seconds: {os.path.basename(trimmed_filepath)}")
        
        # Process the trimmed file
        result = await socket.send_file(trimmed_filepath)
        print("Received API response")
        
        # Save raw results to a JSON file
        base_filename = os.path.basename(filepath)
        result_filename = f"emotion_results/{os.path.splitext(base_filename)[0]}_emotions.json"
        os.makedirs("emotion_results", exist_ok=True)
        
        # Serialize the result object and save it
        try:
            serialized_result = json.dumps(result, default=serialize_predictions, indent=2)
            with open(result_filename, 'w') as f:
                f.write(serialized_result)
            print(f"Saved raw results to {result_filename}")
        except Exception as e:
            print(f"Error saving results: {str(e)}")
            return None
        
        # Process and display emotion results
        try:
            if not result:
                print("No result received from API")
                return None
                
            # Handle StreamModelPredictions object
            if hasattr(result, 'prosody'):
                predictions = result.prosody.predictions
            else:
                print("No prosody data found in result")
                return None
                
            if not predictions:
                print("No predictions found in result")
                return None
                
            emotions = {}
            for pred in predictions:
                if not hasattr(pred, 'emotions'):
                    continue
                    
                for emotion in pred.emotions:
                    if not hasattr(emotion, 'name') or not hasattr(emotion, 'score'):
                        continue
                        
                    name = emotion.name
                    score = emotion.score
                    time = pred.time if hasattr(pred, 'time') else 0
                    
                    if name and score is not None:
                        if name not in emotions:
                            emotions[name] = {'scores': [], 'max_score': 0, 'max_time': 0}
                        emotions[name]['scores'].append(score)
                        if score > emotions[name]['max_score']:
                            emotions[name]['max_score'] = score
                            emotions[name]['max_time'] = time
            
            if emotions:
                # Calculate average scores and sort emotions
                avg_emotions = {name: sum(data['scores'])/len(data['scores']) 
                              for name, data in emotions.items()}
                sorted_emotions = sorted(avg_emotions.items(), key=lambda x: x[1], reverse=True)
                
                # Display results
                print(f"\nResults for {os.path.basename(filepath)}:")
                print(f"Analyzed {len(predictions)} predictions")
                
                print("\nTop 5 emotions (average scores):")
                for emotion, score in sorted_emotions[:5]:
                    print(f"{emotion}: {score:.3f}")
                
                print("\nPeak emotions (score > 0.7):")
                for emotion, data in emotions.items():
                    if data['max_score'] > 0.7:
                        print(f"{emotion}: {data['max_score']:.3f} at {data['max_time']:.1f} seconds")
            else:
                print("No emotions detected in the audio file.")
        except Exception as e:
            print(f"Error processing predictions: {str(e)}")
            return None
            
        return result
        
    except Exception as e:
        print(f"Error processing {filepath}: {str(e)}")
        return None
        
    finally:
        # Clean up temporary files
        if trimmed_filepath:
            try:
                os.remove(trimmed_filepath)
                os.rmdir(os.path.dirname(trimmed_filepath))
            except Exception as e:
                print(f"Error cleaning up temporary files: {str(e)}")

async def main():
    # Load environment variables
    load_dotenv()
    api_key = os.getenv("HUME_API_KEY")
    if not api_key:
        raise ValueError("HUME_API_KEY not found in environment variables")

    # Initialize the client
    client = AsyncHumeClient(api_key=api_key)

    # Configure the prosody model
    model_config = Config(prosody={})
    stream_options = StreamConnectOptions(config=model_config, ssl=ssl_context)

    # Get list of audio files from command line arguments or use all files in directory
    if len(sys.argv) > 1:
        audio_files = sys.argv[1:]
    else:
        audio_dir = "audio_files"
        audio_files = [os.path.join(audio_dir, f) for f in os.listdir(audio_dir) 
                      if f.endswith('.wav') and os.path.getsize(os.path.join(audio_dir, f)) > 100]  # Skip empty files
    
    if not audio_files:
        print("No audio files found to process")
        return
    
    print(f"\nProcessing {len(audio_files)} audio files...")

    # Process all files
    async with client.expression_measurement.stream.connect(options=stream_options) as socket:
        for audio_file in audio_files:
            await process_audio_file(socket, audio_file)

if __name__ == "__main__":
    asyncio.run(main())