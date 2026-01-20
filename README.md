# YouTube Auto-Posting System

Automatically create and upload YouTube videos based on trending topics. This system fetches trending videos, generates content using HeyGen API, optimizes metadata for maximum engagement, and uploads to your YouTube channel.

## Features

- 🔥 **Trend Analysis**: Fetches trending YouTube videos using YouTube Data API
- 🎬 **Video Generation**: Creates videos automatically using HeyGen API
- 📊 **Metadata Optimization**: Generates SEO-optimized titles, descriptions, tags, and hashtags
- 📤 **Auto-Upload**: Uploads videos directly to YouTube with optimized metadata
- 🔄 **Retry Logic**: Handles API errors with exponential backoff retry
- 🔐 **OAuth Authentication**: Secure YouTube API authentication

## Prerequisites

- Python 3.7 or higher
- Google Cloud Project with YouTube Data API v3 enabled
- HeyGen account (free plan available)

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure API Credentials

#### YouTube Data API (Google Cloud)

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the **YouTube Data API v3**
4. Go to **Credentials** → **Create Credentials** → **OAuth client ID**
5. Choose **Desktop app** as the application type
6. Download the credentials JSON file
7. Save it as `client_secrets.json` in the project root

#### HeyGen API

1. Sign up at [HeyGen](https://www.heygen.com/)
2. Go to Settings → API to get your API key
3. Add it to `.env` file (see below)

### 3. Create Environment File

Create a `.env` file in the project root:

```env
HEYGEN_API_KEY=your_heygen_key_here
```

**Important**: Never commit `.env` or `client_secrets.json` to version control!

### 4. First-Time Authentication

On first run, the script will open a browser window for YouTube OAuth authentication. Follow the prompts to authorize access to your YouTube channel.

## Usage

### Basic Usage

```bash
python main.py
```

This will:
1. Fetch trending videos
2. Generate optimized metadata
3. Create a video using HeyGen
4. Upload to YouTube (as private by default)

### Command-Line Options

```bash
# Upload as public video
python main.py --privacy public

# Use a specific region for trends
python main.py --region GB

# Upload an existing video file (skip generation)
python main.py --skip-video-generation --video-file path/to/video.mp4

# Dry run (fetch trends and generate metadata only)
python main.py --dry-run

# Custom output directory for generated videos
python main.py --output-dir my_videos

# Custom category ID
python main.py --category 24  # Entertainment
```

### Privacy Status Options

- `public` - Video is publicly visible
- `private` - Only you can see the video (default)
- `unlisted` - Anyone with the link can see the video

### YouTube Category IDs

Common categories:
- `22` - People & Blogs (default)
- `24` - Entertainment
- `25` - News & Politics
- `26` - Howto & Style
- `27` - Education
- `28` - Science & Technology

See [YouTube API documentation](https://developers.google.com/youtube/v3/docs/videoCategories/list) for full list.

## Project Structure

```
.
├── main.py                 # Main entry point
├── config.py               # Configuration management
├── trends_fetcher.py       # YouTube Data API trends integration
├── content_optimizer.py    # Metadata optimization
├── video_generator.py      # HeyGen API integration
├── youtube_uploader.py     # YouTube Data API integration
├── requirements.txt        # Python dependencies
├── client_secrets.json     # YouTube OAuth credentials (user-provided)
├── .env                    # API keys (user-provided)
└── README.md               # This file
```

## Workflow

1. **Fetch Trends**: Uses YouTube Data API to get trending videos
2. **Analyze Topics**: Extracts keywords and trending topics
3. **Optimize Metadata**: Generates SEO-friendly title, description, tags, and hashtags
4. **Generate Video**: Creates video using HeyGen API with AI avatar/voice
5. **Upload**: Uploads video to YouTube with optimized metadata

## Troubleshooting

### OAuth Authentication Issues

- Ensure `client_secrets.json` is in the project root
- Check that YouTube Data API v3 is enabled in Google Cloud Console
- Delete `youtube-oauth2.json` and re-authenticate if tokens expire

### API Errors

- Verify API keys are correct in `.env` file
- Check API rate limits (free plans have limits)
- Review API documentation for any changes

### Video Generation Issues

- HeyGen API may take several minutes to generate videos
- Check HeyGen dashboard for account status
- Ensure you have sufficient credits/quota

### Upload Failures

- Check video file format (MP4 recommended)
- Verify file size (YouTube has limits)
- Ensure OAuth tokens are valid

## Rate Limits

- **HeyGen**: Free plan has usage limits
- **YouTube Data API**: 10,000 units per day (uploading a video uses ~1600 units, fetching trends uses ~1 unit per request)

## Security Notes

- Never share your API keys or OAuth credentials
- Add `.env`, `client_secrets.json`, and `youtube-oauth2.json` to `.gitignore`
- Use environment variables or secure secret management in production

## License

This project is provided as-is for educational purposes.

## Support

For issues with:
- **YouTube Data API**: [YouTube API Documentation](https://developers.google.com/youtube/v3)
- **HeyGen**: [HeyGen API Documentation](https://docs.heygen.com/)

# scheduled-python-auto
