FROM python:3.11-slim

# Chrome для Pydoll (CDP browser)
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget gnupg2 curl unzip \
    # Chrome dependencies
    fonts-liberation libasound2 libatk-bridge2.0-0 libatk1.0-0 \
    libcups2 libdbus-1-3 libdrm2 libgbm1 libgtk-3-0 libnspr4 \
    libnss3 libx11-xcb1 libxcomposite1 libxdamage1 libxrandr2 \
    xdg-utils libu2f-udev libvulkan1 \
    # Node.js для Claude Code CLI
    nodejs npm \
    && rm -rf /var/lib/apt/lists/*

# Установка Chrome
RUN wget -q -O /tmp/chrome.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb \
    && dpkg -i /tmp/chrome.deb || apt-get install -f -y \
    && rm /tmp/chrome.deb

# Claude Code CLI
RUN npm install -g @anthropic-ai/claude-code

WORKDIR /app

# Python зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Setup Scrapling stealth browsers
RUN python -c "import scrapling; scrapling.setup()" 2>/dev/null || echo "Scrapling setup skipped"

# Код проекта
COPY . .

# Output directory
RUN mkdir -p output

# Claude CLI auth будет mount-иться как volume
VOLUME ["/root/.claude"]
VOLUME ["/app/output"]

ENTRYPOINT ["python", "src/agent.py"]
