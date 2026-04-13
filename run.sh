#!/bin/bash
set -e

echo "Installing dependencies..."
pip install -r requirements.txt --quiet

echo "Setting up Scrapling browsers..."
python -c "import scrapling; scrapling.setup()" 2>/dev/null || echo "Scrapling setup skipped"

echo ""
echo "Tool check:"
python -c "
try:
    from scrapling.fetchers import StealthyFetcher
    print('  Scrapling:  ready')
except: print('  Scrapling:  not available')
try:
    from pydoll.browser.chromium import Chromium
    print('  Pydoll:     ready')
except: print('  Pydoll:     not available (optional)')
"

if command -v claude &> /dev/null; then
    echo "  Claude CLI: ready"
else
    echo "  Claude CLI: not found (AI will use regex fallback)"
fi

echo ""
echo "Starting 4-Level Cascade..."
cd src && python agent.py "$@"

echo ""
echo "Results:"
ls -la ../output/
