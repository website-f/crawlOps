# Playwright "noble" image = Ubuntu 24.04 (Python 3.12, which browser-use needs) with
# Chromium + all system deps preinstalled. browser-use drives that Chromium over CDP
# via BrowserProfile.executable_path — no pip playwright browser install needed.
FROM mcr.microsoft.com/playwright/python:v1.47.0-noble

WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# record the preinstalled chromium path for the app to pass as executable_path
RUN echo "CHROMIUM_PATH=$(ls -d /ms-playwright/chromium-*/chrome-linux/chrome | head -1)" > /srv/chromium.env \
    && cat /srv/chromium.env

COPY app.py .
ENV PYTHONUNBUFFERED=1
EXPOSE 8600
CMD ["sh", "-c", "export $(cat /srv/chromium.env) && uvicorn app:app --host 0.0.0.0 --port 8600"]
