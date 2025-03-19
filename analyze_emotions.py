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
    """Trim audio file to 5 seconds if longer."""
    temp_dir = tempfile.mkdtemp()
    base_filename = os.path.basename(filepath)
    trimmed_filepath = os.path.join(temp_dir, f"trimmed_{base_filename}")
    
    # Use sox to trim the audio file
    os.system(f'sox "{filepath}" "{trimmed_filepath}" trim 0 5.0')
    
    return trimmed_filepath

async def process_audio_file(socket, filepath):
    """Process a single audio file and analyze emotions."""
    try:
        print(f"\nProcessing {os.path.basename(filepath)}...")
        
        # Trim audio file if needed
        trimmed_filepath = trim_audio(filepath)
        print(f"Trimmed to 5 seconds: {os.path.basename(trimmed_filepath)}")
        
        # Process the trimmed file
        result = await socket.send_file(trimmed_filepath)
        
        # Clean up temporary file
        os.remove(trimmed_filepath)
        os.rmdir(os.path.dirname(trimmed_filepath))
        
        # Save raw results to a JSON file
        base_filename = os.path.basename(filepath)
        result_filename = f"emotion_results/{os.path.splitext(base_filename)[0]}_emotions.json"
        os.makedirs("emotion_results", exist_ok=True)
        
        # Serialize the result object
        serialized_result = json.dumps(result, default=serialize_predictions, indent=2)
        with open(result_filename, 'w') as f:
            f.write(serialized_result)
        
        # Process and display emotion results
        if result and hasattr(result, 'prosody') and hasattr(result.prosody, 'predictions'):
            predictions = result.prosody.predictions
            emotions = {}
            
            # Aggregate emotions across all predictions
            for pred in predictions:
                if hasattr(pred, 'emotions'):
                    for emotion in pred.emotions:
                        if hasattr(emotion, 'name') and hasattr(emotion, 'score'):
                            name = emotion.name
                            score = emotion.score
                            time = pred.time if hasattr(pred, 'time') else 0
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
        else:
            print("No valid predictions found in the result.")
        
        return result
    except Exception as e:
        print(f"Error processing {filepath}: {str(e)}")
        # Clean up temporary files in case of error
        if 'trimmed_filepath' in locals():
            try:
                os.remove(trimmed_filepath)
                os.rmdir(os.path.dirname(trimmed_filepath))
            except:
                pass
        return None

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

    # Get list of audio files
    audio_dir = "audio_files"
    audio_files = [os.path.join(audio_dir, f) for f in os.listdir(audio_dir) 
                  if f.endswith('.wav') and os.path.getsize(os.path.join(audio_dir, f)) > 100]  # Skip empty files
    
    if not audio_files:
        print("No audio files found in the audio_files directory")
        return
    
    # Process only the first file for testing
    test_file = audio_files[0]
    print(f"Testing with file: {os.path.basename(test_file)}")

    # Process the test file
    async with client.expression_measurement.stream.connect(options=stream_options) as socket:
        await process_audio_file(socket, test_file)

if __name__ == "__main__":
    asyncio.run(main())