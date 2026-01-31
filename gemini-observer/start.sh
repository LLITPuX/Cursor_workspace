#!/bin/bash
set -e

# Ensure credentials directory exists
mkdir -p credentials

# Check if token exists
if [ ! -f "credentials/token.json" ]; then
    echo "----------------------------------------------------------------"
    echo "⚠️  TOKEN NOT FOUND. STARTING AUTHENTICATION..."
    echo "----------------------------------------------------------------"
    echo "Please open the link below in your browser locally."
    echo "Since this is running in Docker, make sure port 8080 is mapped."
    echo "----------------------------------------------------------------"
    
    python scripts/auth_google.py
fi

echo "----------------------------------------------------------------"
echo "🚀 STARTING GEMINI OBSERVER..."
echo "----------------------------------------------------------------"

python main.py
