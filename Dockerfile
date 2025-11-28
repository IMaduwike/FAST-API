# 1️⃣ Use official Python base image
FROM python:3.11-slim

# 2️⃣ Set working directory
WORKDIR /app

# 3️⃣ Install system dependencies (ffmpeg, git removed since you don’t need it)
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

# 4️⃣ Copy project files into container
COPY . .

# 5️⃣ Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# 6️⃣ Install Playwright and ONLY Chromium
RUN pip install playwright && playwright install chromium

# 7️⃣ Expose FastAPI port (default 8000)
EXPOSE 8000

# 8️⃣ Start your FastAPI app (change if your entrypoint is different)
CMD ["python", "app.py"]