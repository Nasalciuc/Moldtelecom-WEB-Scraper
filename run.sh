#!/bin/bash
set -e

echo "🔧 Installing dependencies..."
pip install -r requirements.txt --quiet

echo "🔍 Checking Claude Code CLI..."
if ! command -v claude &> /dev/null; then
    echo "⚠️  Claude Code CLI not found!"
    echo "   Install: npm install -g @anthropic-ai/claude-code"
    echo "   Login:   claude login"
    echo "   AI extraction will use regex fallback."
else
    echo "✅ Claude CLI found"
fi

echo "🚀 Starting Moldtelecom AI Scraping Agent..."
cd src && python agent.py "$@"

echo ""
echo "📂 Results in output/ directory:"
ls -la ../output/
