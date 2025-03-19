# Omi - Emotion Analysis Server

A Flask-based server that receives audio recordings from the Omi wearable device and analyzes emotions using the Hume AI SDK. The server provides real-time emotion analysis results through a web interface.

## Features

- Audio recording reception via HTTP POST endpoint
- Emotion analysis using Hume AI's prosody model
- Web interface for viewing emotion analysis results
- Real-time processing of 5-second audio clips from Omi wearable
- Support for WAV audio format (16-bit, mono, 16kHz)
- Local deployment with Flask
- Public deployment option using ngrok

## Prerequisites

- Python 3.10 or higher
- Hume AI API key
- SoX (for audio processing)
- ngrok (for public deployment)

## Installation

1. Clone the repository:
```bash
git clone <your-repo-url>
cd omi
```

2. Install required Python packages:
```bash
pip3 install -r requirements.txt
```

3. Install SoX (for audio processing):
```bash
# On macOS
brew install sox

# On Ubuntu/Debian
sudo apt-get install sox

# On Windows (using Chocolatey)
choco install sox
```

4. Create a `.env` file in the project root and add your Hume AI API key:
```
HUME_API_KEY=your_api_key_here
```

5. Install ngrok (optional, for public deployment):
```bash
# On macOS
brew install ngrok

# On Ubuntu/Debian
snap install ngrok

# On Windows (using Chocolatey)
choco install ngrok
```

## Project Structure

```
omi/
├── app.py                 # Main Flask server
├── analyze_emotions.py    # Emotion analysis script
├── templates/            
│   └── emotions.html     # Web interface template
├── audio_files/          # Stored audio recordings
├── emotion_results/      # Emotion analysis results
├── requirements.txt      # Python dependencies
└── README.md            # This file
```

## Deployment

### Local Deployment
1. Start the Flask server:
```bash
python3 app.py
```

The server will be available at:
- Main interface: http://localhost:8000/
- Emotion results: http://localhost:8000/emotions
- Audio endpoint: http://localhost:8000/audio (POST)

### Public Deployment
1. Start the Flask server as shown above
2. In a new terminal, create a public URL with ngrok:
```bash
ngrok http 8000
```
3. ngrok will provide a public URL (e.g., `https://your-unique-id.ngrok.io`)
4. Use this URL as your endpoint in the Omi wearable configuration

## Omi Wearable Integration

1. Configure your Omi wearable to send audio data to your server:
   - For local testing: `http://localhost:8000/audio`
   - For remote access: `https://your-ngrok-url/audio`
2. The Omi device will send 5-second audio clips to your server
3. Each clip will be automatically processed for emotion analysis
4. View the results in real-time at the `/emotions` endpoint

## API Endpoints

- `POST /audio`: Receives audio data from Omi wearable
  - Input: Raw audio data (WAV format, 5-second clips)
  - Output: JSON with filename and timestamp

- `GET /emotions`: Displays emotion analysis results
  - Output: Web interface showing analyzed emotions

## Development

- The server runs in debug mode by default
- Audio files are saved in the `audio_files` directory
- Emotion analysis results are saved in the `emotion_results` directory
- Logs are saved to `omi_server.log`
- Server listens on port 8000 by default

## Troubleshooting

- If port 8000 is already in use, you can modify the port in `app.py`
- For ngrok connection issues, ensure your Flask server is running before starting ngrok
- Check the logs in `omi_server.log` for detailed error messages

## License

[Your chosen license]

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request 