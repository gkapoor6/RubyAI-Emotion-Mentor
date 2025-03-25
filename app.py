from flask import Flask, request, jsonify, render_template
import os
from datetime import datetime, timedelta
import wave
import logging
import json
from pathlib import Path
from dotenv import load_dotenv
import math
import asyncio
import random

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('omi_server.log') if not os.getenv('VERCEL_ENV') else logging.StreamHandler(),
        logging.StreamHandler()
    ]
)

app = Flask(__name__)

# Create directories if they don't exist and we're not on Vercel
if not os.getenv('VERCEL_ENV'):
    AUDIO_DIR = "audio_files"
    RESULTS_DIR = "emotion_results"
    for directory in [AUDIO_DIR, RESULTS_DIR]:
        if not os.path.exists(directory):
            os.makedirs(directory)
else:
    # On Vercel, use temporary storage
    AUDIO_DIR = "/tmp/audio_files"
    RESULTS_DIR = "/tmp/emotion_results"
    for directory in [AUDIO_DIR, RESULTS_DIR]:
        if not os.path.exists(directory):
            os.makedirs(directory)

@app.route('/')
def home():
    return render_template('emotions.html', results=[])

def get_timestamp_from_filename(filename):
    """Extract timestamp from filename format: audio_YYYYMMDD_HHMMSS"""
    parts = filename.split('_')
    if len(parts) >= 3:
        date_str = parts[1]  # YYYYMMDD
        time_str = parts[2].split('.')[0]  # HHMMSS (remove .wav)
        
        # Format the datetime
        year = date_str[:4]
        month = date_str[4:6]
        day = date_str[6:]
        hour = time_str[:2]
        minute = time_str[2:4]
        second = time_str[4:6]
        
        return datetime.strptime(f"{year}-{month}-{day} {hour}:{minute}:{second}", '%Y-%m-%d %H:%M:%S')
    return None

@app.route('/emotions')
def show_emotions():
    results = []
    results_dir = Path(RESULTS_DIR)
    
    # Get all JSON files in the results directory
    json_files = sorted(results_dir.glob('*_emotions.json'), reverse=True)
    
    # Group files by 20-minute intervals
    interval_groups = {}
    for json_file in json_files:
        try:
            # Extract timestamp from filename (format: audio_YYYYMMDD_HHMMSS)
            filename = json_file.stem  # e.g., audio_20250318_161126_emotions
            parts = filename.replace('_emotions', '').split('_')
            if len(parts) >= 3:
                date_str = parts[1]  # YYYYMMDD
                time_str = parts[2]  # HHMMSS
                
                # Format the datetime properly
                year = date_str[:4]
                month = date_str[4:6]
                day = date_str[6:]
                hour = time_str[:2]
                minute = time_str[2:4]
                second = time_str[4:6]
                
                timestamp = datetime.strptime(f"{year}-{month}-{day} {hour}:{minute}:{second}", '%Y-%m-%d %H:%M:%S')
                
                # Create 20-minute interval key (floor to nearest 20 minutes)
                interval_key = timestamp.replace(
                    minute=20 * (timestamp.minute // 20),
                    second=0
                )
                
                if interval_key not in interval_groups:
                    interval_groups[interval_key] = []
                interval_groups[interval_key].append((timestamp, json_file))
            
        except Exception as e:
            logging.error(f"Error processing filename {json_file}: {str(e)}")
            continue
    
    # Process each interval group
    for interval, files in sorted(interval_groups.items(), reverse=True):
        # Sort files by timestamp within interval
        sorted_files = sorted(files, key=lambda x: x[0])
        
        # If more than 5 files in the interval, take evenly spaced samples
        selected_files = []
        if len(sorted_files) > 5:
            step = len(sorted_files) // 5
            for i in range(0, len(sorted_files), step):
                if len(selected_files) < 5:  # Ensure we don't get more than 5
                    selected_files.append(sorted_files[i][1])
        else:
            selected_files = [f[1] for f in sorted_files]
        
        # Process the selected files
        for json_file in selected_files:
            try:
                with open(json_file, 'r') as f:
                    data = json.load(f)
                
                # Skip files that only contain error messages
                if 'error' in data and 'prosody' not in data:
                    continue
                    
                # Process files with valid emotion data
                if isinstance(data, dict) and 'prosody' in data:
                    # Extract timestamp from filename
                    filename = json_file.stem
                    parts = filename.replace('_emotions', '').split('_')
                    if len(parts) >= 3:
                        date_str = parts[1]
                        time_str = parts[2]
                        
                        # Format the datetime properly
                        year = date_str[:4]
                        month = date_str[4:6]
                        day = date_str[6:]
                        hour = time_str[:2]
                        minute = time_str[2:4]
                        second = time_str[4:6]
                        
                        timestamp = datetime.strptime(f"{year}-{month}-{day} {hour}:{minute}:{second}", '%Y-%m-%d %H:%M:%S')
                        formatted_timestamp = timestamp.strftime('%-I:%M %p')
                        
                        # Process emotions data
                        predictions = data['prosody'].get('predictions', [])
                        if predictions and len(predictions) > 0:
                            # Get emotions from the first prediction
                            prediction = predictions[0]
                            if 'emotions' in prediction:
                                # Sort emotions by score and get top 5
                                emotions = prediction['emotions']
                                top_emotions = sorted(
                                    emotions,
                                    key=lambda x: x['score'],
                                    reverse=True
                                )[:5]
                                
                                results.append({
                                    'timestamp': formatted_timestamp,
                                    'emotions': top_emotions
                                })
            
            except Exception as e:
                logging.error(f"Error processing {json_file}: {str(e)}")
                continue
    
    # Sort results by timestamp
    def parse_timestamp(timestamp_str):
        try:
            return datetime.strptime(timestamp_str, '%I:%M %p').replace(
                year=datetime.now().year,
                month=datetime.now().month,
                day=datetime.now().day
            )
        except ValueError:
            return datetime.min

    # Sort results by timestamp
    results.sort(key=lambda x: parse_timestamp(x['timestamp']))
    
    # Return JSON data
    return jsonify(results)

@app.route('/emotions/view')
def view_emotions():
    return render_template('emotions.html')

@app.route('/audio', methods=['POST'])
def receive_audio():
    try:
        # Get the raw audio data from the request
        audio_data = request.get_data()
        
        if not audio_data:
            return jsonify({"error": "No audio data received"}), 400
        
        # Generate a unique filename using timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"audio_{timestamp}.wav"
        filepath = os.path.join(AUDIO_DIR, filename)
        
        # Save the audio data as a WAV file
        with wave.open(filepath, 'wb') as wav_file:
            # Set WAV parameters (adjust these based on your device's specifications)
            wav_file.setnchannels(1)  # Mono
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(16000)  # 16kHz
            wav_file.writeframes(audio_data)
        
        # Log the file size and timing information
        file_size = os.path.getsize(filepath) / 1024  # Convert to KB
        logging.info(f"Received audio file: {filename}")
        logging.info(f"File size: {file_size:.2f} KB")
        logging.info(f"Timestamp: {timestamp}")
        
        return jsonify({
            "message": "Audio data received and saved successfully",
            "filename": filename,
            "timestamp": timestamp,
            "file_size_kb": round(file_size, 2)
        }), 200
        
    except Exception as e:
        logging.error(f"Error processing audio: {str(e)}")
        return jsonify({"error": str(e)}), 500

# Health check endpoint for Vercel
@app.route('/health')
def health_check():
    return jsonify({"status": "healthy"}), 200

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8000, debug=True) 