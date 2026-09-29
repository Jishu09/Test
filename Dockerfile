FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && apt-get install -y ffmpeg aria2 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Grant execute permission to your script
RUN chmod +x start.sh

EXPOSE 8011

# Use the script as the entry point
CMD ["./start.sh"]