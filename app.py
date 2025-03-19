from flask import Flask, request, jsonify, render_template
import os
from datetime import datetime
import wave
import logging
import json
from pathlib import Path
from dotenv import load_dotenv

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

@app.route('/emotions')
def show_emotions():
    results = []
    results_dir = Path(RESULTS_DIR)
    
    # Get all JSON files in the results directory
    json_files = sorted(results_dir.glob('*_emotions.json'), reverse=True)
    
    for json_file in json_files:
        try:
            with open(json_file, 'r') as f:
                data = json.load(f)
            
            # Extract timestamp from filename (format: audio_YYYYMMDD_HHMMSS)
            filename = json_file.stem  # e.g., audio_20250318_161126_emotions
            parts = filename.split('_')
            if len(parts) >= 3:
                date_str = parts[1]  # YYYYMMDD
                time_str = parts[2]  # HHMMSS
                
                # Format the date string properly
                year = date_str[:4]
                month = date_str[4:6]
                day = date_str[6:]
                hour = time_str[:2]
                minute = time_str[2:4]
                second = time_str[4:6]
                
                timestamp = datetime.strptime(f"{year}-{month}-{day} {hour}:{minute}:{second}", '%Y-%m-%d %H:%M:%S')
                formatted_timestamp = timestamp.strftime('%B %d, %Y at %I:%M:%S %p')
                
                # Process emotions data
                if isinstance(data, dict) and 'prosody' in data:
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
    
    return render_template('emotions.html', results=results)

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

if __name__ == '__main__':
    port = int(os.getenv('PORT', 8000))
    if os.getenv('VERCEL_ENV'):
        app.run()
    else:
        # Try different ports if the default is in use
        while port < 8010:
            try:
                app.run(host='0.0.0.0', port=port, debug=True)
                break
            except OSError:
                logging.warning(f"Port {port} is in use, trying port {port + 1}")
                port += 1
        if port == 8010:
            logging.error("Could not find an available port between 8000 and 8009") 