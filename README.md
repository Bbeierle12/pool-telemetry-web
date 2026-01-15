# Pool Telemetry Web

AI-powered pool/billiards game analysis and telemetry system. Record your games, track shots, and get real-time coaching feedback using computer vision and AI.

## Features

- **Video Recording** - Record sessions from GoPro (WiFi/USB) or upload video files
- **Real-time Ball Tracking** - AI-powered detection of ball positions and movements
- **Shot Analysis** - Automatic shot detection with physics validation
- **AI Coaching** - Get personalized feedback using Google Gemini and Claude
- **Statistics Dashboard** - Track your performance over time
- **Multi-user Profiles** - Support for multiple players/family members
- **Export** - Export session data as JSON, CSV, or JSONL

## Tech Stack

**Backend:**
- FastAPI (Python 3.11)
- SQLAlchemy 2.0 with async support
- SQLite (default) / PostgreSQL
- WebSocket for real-time updates

**Frontend:**
- React 18 with TypeScript
- Zustand for state management
- TailwindCSS
- HLS.js for video streaming

**AI/ML:**
- Google Gemini for video analysis
- Anthropic Claude for coaching feedback
- OpenCV for video processing

## Quick Start

### Using Docker (Recommended)

1. Clone the repository:
```bash
git clone https://github.com/yourusername/pool-telemetry-web.git
cd pool-telemetry-web
```

2. Copy the environment file and add your API keys:
```bash
cp .env.example .env
# Edit .env and add your GEMINI_API_KEY and ANTHROPIC_API_KEY
```

3. Start the application:
```bash
docker-compose up -d
```

4. Open http://localhost in your browser

### Manual Setup

#### Backend

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the server
uvicorn app.main:app --reload --port 8000
```

#### Frontend

```bash
cd frontend

# Install dependencies
npm install

# Run development server
npm run dev
```

## Configuration

Create a `.env` file in the root directory:

```env
# Required for AI features
GEMINI_API_KEY=your_gemini_api_key
ANTHROPIC_API_KEY=your_anthropic_api_key

# Optional
SECRET_KEY=your_secret_key_for_jwt
DATABASE_URL=sqlite+aiosqlite:///./data/pool_telemetry.db
```

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `GEMINI_API_KEY` | Google Gemini API key for video analysis | None |
| `ANTHROPIC_API_KEY` | Anthropic API key for coaching | None |
| `SECRET_KEY` | JWT signing key | Auto-generated |
| `DATABASE_URL` | Database connection string | SQLite |
| `DATA_DIRECTORY` | Path for data storage | `./data` |

## API Documentation

Once running, access the interactive API docs at:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### Key Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/auth/profiles` | GET, POST | Manage user profiles |
| `/api/auth/login` | POST | Authenticate with PIN |
| `/api/sessions` | GET, POST | List/create sessions |
| `/api/sessions/{id}/start` | POST | Start recording |
| `/api/sessions/{id}/stop` | POST | Stop recording |
| `/api/video/upload` | POST | Upload video file |
| `/api/coaching/feedback` | POST | Get AI coaching |
| `/ws/events/{session_id}` | WebSocket | Real-time events |

## Project Structure

```
pool-telemetry-web/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── routes/      # REST endpoints
│   │   │   └── websockets/  # WebSocket handlers
│   │   ├── core/            # Database setup
│   │   ├── models/          # SQLAlchemy models
│   │   ├── services/        # Business logic
│   │   └── config.py        # Configuration
│   ├── tests/               # Backend tests
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/      # React components
│   │   ├── hooks/           # Custom hooks
│   │   ├── store/           # Zustand stores
│   │   ├── services/        # API client
│   │   └── types/           # TypeScript types
│   └── package.json
├── docker-compose.yml
├── nginx.conf
└── README.md
```

## Testing

### Backend Tests
```bash
cd backend
pytest                    # Run all tests
pytest -v                 # Verbose output
pytest --cov=app          # With coverage
```

### Frontend Tests
```bash
cd frontend
npm test                  # Watch mode
npm run test:run          # Single run
npm run test:coverage     # With coverage
```

## Usage Guide

### Creating a Profile

1. Open the app and click "Create Profile"
2. Enter your name and a 4-6 digit PIN
3. The first profile created becomes the admin

### Recording a Session

1. Log in with your profile
2. Click "New Session"
3. Choose video source:
   - **GoPro WiFi** - Connect to GoPro's WiFi network
   - **GoPro USB** - Connect via USB cable
   - **Upload** - Upload an existing video file
4. Click "Start Recording"
5. Play your game - the AI will track shots automatically
6. Click "Stop" when finished

### Viewing Statistics

- Real-time stats appear during recording
- Access historical sessions from the Sessions browser
- Export data for external analysis

## Cost Management

AI features use paid APIs. The app tracks costs and has built-in limits:

- **Warning threshold**: $5.00 per session
- **Stop threshold**: $10.00 per session

Monitor costs in the Settings panel.

## Troubleshooting

### GoPro not connecting
- Ensure you're connected to the GoPro's WiFi network
- Check that the GoPro is in "App Mode"

### Video not playing
- Verify FFmpeg is installed (required for HLS conversion)
- Check browser console for errors

### AI analysis not working
- Verify API keys are set in `.env`
- Check API quota/billing status

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- [FastAPI](https://fastapi.tiangolo.com/) - Modern Python web framework
- [React](https://react.dev/) - UI library
- [Google Gemini](https://ai.google.dev/) - Video analysis AI
- [Anthropic Claude](https://www.anthropic.com/) - Coaching AI
