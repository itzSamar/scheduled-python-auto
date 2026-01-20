# Quick Start Guide

Follow these steps to get your YouTube Auto-Posting System up and running.

## Step 1: Install Python Dependencies

```bash
pip install -r requirements.txt
```

Or if you prefer using a virtual environment:

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Step 2: Get API Credentials

### A. YouTube Data API (Google Cloud)

1. Go to https://console.cloud.google.com/
2. Create a new project (or select existing)
3. Enable **YouTube Data API v3**:
   - Go to "APIs & Services" → "Library"
   - Search for "YouTube Data API v3"
   - Click "Enable"
4. Create OAuth 2.0 credentials:
   - Go to "APIs & Services" → "Credentials"
   - Click "Create Credentials" → "OAuth client ID"
   - If prompted, configure OAuth consent screen first
   - Choose "Desktop app" as application type
   - Download the JSON file
   - Rename it to `client_secrets.json` and place in project root

### B. HeyGen API

1. Sign up at https://www.heygen.com/
2. Go to Settings → API (or Subscriptions & API → HeyGen API)
3. Copy your API token/key
4. Add it to `.env` file (see Step 3)

## Step 3: Configure Environment Variables

Run the setup script:

```bash
./setup_env.sh
```

Or manually create `.env` file:

```bash
cat > .env << 'EOF'
HEYGEN_API_KEY=your_heygen_key_here
EOF
```

Then edit `.env` and add your actual API keys.

## Step 4: First Run (Authentication)

Run the script for the first time. It will:

1. Open a browser window for YouTube OAuth authentication
2. Ask you to sign in and authorize the application
3. Save credentials for future use

```bash
python3 main.py --dry-run
```

The `--dry-run` flag lets you test without creating/uploading videos.

## Step 5: Test Full Workflow

Once everything is configured, run:

```bash
python3 main.py --privacy private
```

This will:
- Fetch trending videos
- Generate optimized metadata
- Create a video using HeyGen
- Upload to YouTube (as private)

## Common Commands

```bash
# Dry run (test without uploading)
python3 main.py --dry-run

# Upload as public video
python3 main.py --privacy public

# Use different region for trends
python3 main.py --region GB

# Upload existing video file
python3 main.py --skip-video-generation --video-file my_video.mp4 --privacy public
```

## Troubleshooting

### "client_secrets.json not found"
- Make sure you downloaded OAuth credentials from Google Cloud Console
- Rename the file to `client_secrets.json`
- Place it in the project root directory

### "API key not set"
- Check your `.env` file exists
- Verify API keys are correct (no extra spaces)
- Make sure you're using the correct variable names

### "Authentication failed"
- Delete `youtube-oauth2.json` and try again
- Check that YouTube Data API v3 is enabled in Google Cloud Console
- Verify OAuth consent screen is configured

### "Video generation failed"
- Check HeyGen API key is correct
- Verify you have credits/quota available
- Check HeyGen API status

## Next Steps

- Customize video content in `content_optimizer.py`
- Adjust video generation settings in `video_generator.py`
- Modify trend analysis in `trends_fetcher.py`
- Set up automated scheduling (cron job, etc.)

## Need Help?

- Check the main [README.md](README.md) for detailed documentation
- Review API documentation:
  - [YouTube Data API](https://developers.google.com/youtube/v3)
  - [HeyGen API](https://docs.heygen.com/)

