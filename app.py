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
from claude_insights import get_emotion_insights
import subprocess

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
    today = datetime.now().strftime('%Y%m%d')
    
    # Get all JSON files in the results directory from today
    json_files = sorted(
        [f for f in results_dir.glob('*_emotions.json') 
         if f.stem.split('_')[1] == today],
        reverse=True
    )
    
    if not json_files:
        logging.info("No emotion results found for today")
        return jsonify([])
    
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
    
    if not interval_groups:
        logging.info("No valid interval groups found")
        return jsonify([])
    
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
        
        logging.info(f"Processing interval {interval} with {len(selected_files)} files")
        
        # Find the file with highest emotion intensity in this interval
        max_intensity = 0
        max_intensity_file = None
        max_intensity_data = None
        
        for json_file in selected_files:
            try:
                with open(json_file, 'r') as f:
                    data = json.load(f)
                
                # Skip files that only contain error messages
                if 'error' in data and 'prosody' not in data:
                    logging.warning(f"Skipping error-only file: {json_file}")
                    continue
                    
                # Process files with valid emotion data
                if isinstance(data, dict) and 'prosody' in data:
                    predictions = data['prosody'].get('predictions', [])
                    if predictions and len(predictions) > 0:
                        prediction = predictions[0]
                        if 'emotions' in prediction:
                            # Find the highest emotion intensity in this file
                            emotions = prediction['emotions']
                            max_file_intensity = max(emotion['score'] for emotion in emotions)
                            
                            if max_file_intensity > max_intensity:
                                max_intensity = max_file_intensity
                                max_intensity_file = json_file
                                max_intensity_data = data
                                logging.info(f"New max intensity found: {max_intensity} in {json_file.name}")
            
            except Exception as e:
                logging.error(f"Error processing {json_file}: {str(e)}")
                continue
        
        # If we found a file with valid emotions, add it to results
        if max_intensity_file and max_intensity_data:
            try:
                # Extract timestamp from filename
                filename = max_intensity_file.stem
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
                    
                    # Get emotions from the file with highest intensity
                    predictions = max_intensity_data['prosody'].get('predictions', [])
                    if predictions and len(predictions) > 0:
                        prediction = predictions[0]
                        if 'emotions' in prediction:
                            # Sort emotions by score and get top 3
                            emotions = prediction['emotions']
                            top_emotions = sorted(
                                emotions,
                                key=lambda x: x['score'],
                                reverse=True
                            )[:3]
                            
                            results.append({
                                'timestamp': formatted_timestamp,
                                'emotions': top_emotions,
                                'max_intensity': max_intensity
                            })
                            logging.info(f"Added emotions for {formatted_timestamp} with max intensity {max_intensity}")
            
            except Exception as e:
                logging.error(f"Error processing max intensity file {max_intensity_file}: {str(e)}")
    
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
    
    logging.info(f"Returning {len(results)} emotion results")
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
        
        # Process the audio file with Hume AI
        try:
            logging.info(f"Starting emotion analysis for {filename}")
            process = subprocess.run(
                ['python3', 'analyze_emotions.py', filepath],
                capture_output=True,
                text=True,
                timeout=30  # Set a timeout of 30 seconds
            )
            
            if process.returncode != 0:
                logging.error(f"Emotion analysis failed for {filename}")
                logging.error(f"Error output: {process.stderr}")
                return jsonify({
                    "message": "Audio received but emotion analysis failed",
                    "filename": filename,
                    "timestamp": timestamp,
                    "file_size_kb": round(file_size, 2),
                    "error": process.stderr
                }), 500
            
            logging.info(f"Emotion analysis completed for {filename}")
            logging.info(f"Analysis output: {process.stdout}")
            
        except subprocess.TimeoutExpired:
            logging.error(f"Emotion analysis timed out for {filename}")
            return jsonify({
                "message": "Audio received but emotion analysis timed out",
                "filename": filename,
                "timestamp": timestamp,
                "file_size_kb": round(file_size, 2)
            }), 500
        except Exception as e:
            logging.error(f"Error during emotion analysis: {str(e)}")
            return jsonify({
                "message": "Audio received but emotion analysis failed",
                "filename": filename,
                "timestamp": timestamp,
                "file_size_kb": round(file_size, 2),
                "error": str(e)
            }), 500
        
        return jsonify({
            "message": "Audio data received and processed successfully",
            "filename": filename,
            "timestamp": timestamp,
            "file_size_kb": round(file_size, 2)
        }), 200
        
    except Exception as e:
        logging.error(f"Error processing audio: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/emotions/insights')
def get_insights():
    try:
        # Get emotion data from the /emotions endpoint
        with app.test_client() as client:
            response = client.get('/emotions')
            emotion_data = json.loads(response.data)
        
        # Generate insights using Claude
        insights = get_emotion_insights(emotion_data)
        return jsonify(insights)
    
    except Exception as e:
        logging.error(f"Error getting insights: {str(e)}")
        return jsonify({
            "error": "Unable to generate insights at this time.",
            "timestamp": datetime.now().strftime("%I:%M %p")
        })

# Health check endpoint for Vercel
@app.route('/health')
def health_check():
    return jsonify({"status": "healthy"}), 200

def process_unprocessed_audio_files():
    """Process 5 random files per 20-minute interval from today's audio files."""
    try:
        audio_dir = Path(AUDIO_DIR)
        results_dir = Path(RESULTS_DIR)
        today = datetime.now().strftime('%Y%m%d')
        
        # Get all audio files from today
        audio_files = [f for f in audio_dir.glob('*.wav') 
                      if f.stem.split('_')[1] == today]
        
        if not audio_files:
            logging.info("No audio files found for today")
            return
            
        # Get all existing emotion result files
        existing_results = {f.stem.replace('_emotions', '') 
                          for f in results_dir.glob('*_emotions.json')}
        
        # Group files by 20-minute intervals
        interval_groups = {}
        for audio_file in audio_files:
            try:
                # Extract timestamp from filename (format: audio_YYYYMMDD_HHMMSS)
                parts = audio_file.stem.split('_')
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
                    interval_groups[interval_key].append(audio_file)
                
            except Exception as e:
                logging.error(f"Error processing filename {audio_file}: {str(e)}")
                continue
        
        if not interval_groups:
            logging.info("No valid interval groups found")
            return
            
        # Process each interval group
        for interval, files in sorted(interval_groups.items(), reverse=True):
            # Randomly select up to 5 files from this interval
            selected_files = random.sample(files, min(5, len(files)))
            logging.info(f"Selected {len(selected_files)} files for interval {interval}")
            
            # Process only unprocessed files
            for audio_file in selected_files:
                if audio_file.stem not in existing_results:
                    try:
                        logging.info(f"Processing {audio_file.name}")
                        process = subprocess.run(
                            ['python3', 'analyze_emotions.py', str(audio_file)],
                            capture_output=True,
                            text=True,
                            timeout=30
                        )
                        
                        if process.returncode != 0:
                            logging.error(f"Failed to process {audio_file.name}")
                            logging.error(f"Error: {process.stderr}")
                        else:
                            logging.info(f"Successfully processed {audio_file.name}")
                            
                    except Exception as e:
                        logging.error(f"Error processing {audio_file.name}: {str(e)}")
                else:
                    logging.info(f"Skipping already processed file: {audio_file.name}")
                    
    except Exception as e:
        logging.error(f"Error in process_unprocessed_audio_files: {str(e)}")

if __name__ == "__main__":
    # Process any unprocessed files before starting the server
    process_unprocessed_audio_files()
    app.run(host='0.0.0.0', port=8000, debug=True) 