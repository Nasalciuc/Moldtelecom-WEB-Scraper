#!/bin/bash
set -e

echo "🔧 Installing dependencies..."
pip install -r requirements.txt --quiet

echo "🔍 Checking .env..."
if [ ! -f .env ]; then
    echo "⚠️  No .env file found. Copying from .env.example"
    cp .env.example .env
    echo "   Edit .env and add your ANTHROPIC_API_KEY"
fi

echo "🚀 Starting Moldtelecom AI Scraping Agent..."
cd src && python agent.py "$@"

echo ""
echo "📂 Results in output/ directory:"
ls -la ../output/
