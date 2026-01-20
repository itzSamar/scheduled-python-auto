#!/bin/bash
# Setup script to create .env file from template

if [ ! -f .env ]; then
    echo "Creating .env file from template..."
    cat > .env << 'EOF'
# API Keys Configuration
# Fill in your actual API keys below

# HeyGen API Key
# Get it from: https://www.heygen.com/ → Settings → API
HEYGEN_API_KEY=
EOF
    echo ".env file created! Please edit it and add your API keys."
else
    echo ".env file already exists. Skipping creation."
fi

