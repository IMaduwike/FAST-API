# 1️⃣ Use official Python base image
FROM python:3.11-slim

# 2️⃣ Set working directory
WORKDIR /app

# 3️⃣ Install system dependencies for Playwright + ffmpeg + git
RUN apt-get update && apt-get install -y git ffmpeg && rm -rf /var/lib/apt/lists/*

# 4️⃣ Clone your repo
RUN git clone https://github.com/ayanokojix-1/FAST-API /app

# 5️⃣ Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# 6️⃣ Install Playwright and Chromium only
RUN pip install playwright && playwright install chromium

# 7️⃣ Expose Flask port
EXPOSE 8000

# 8️⃣ Start your app
CMD ["python", "app.py"]