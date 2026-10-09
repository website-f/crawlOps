# Python 3.12 (browser-use needs >=3.11). We install Playwright's Chromium and point
# browser-use at it via BrowserProfile.executable_path — browser-use 0.13 drives it
# over CDP, no Playwright runtime needed beyond the binary + system deps.
FROM python:3.12-slim

WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && playwright install --with-deps chromium

# resolve the chromium binary path once, at build time, into an env the app reads
RUN echo "CHROMIUM_PATH=$(find /root/.cache/ms-playwright -name chrome -type f | head -1)" > /srv/chromium.env \
    && cat /srv/chromium.env

COPY app.py .
ENV PYTHONUNBUFFERED=1
EXPOSE 8600
CMD ["sh", "-c", "export $(cat /srv/chromium.env) && uvicorn app:app --host 0.0.0.0 --port 8600"]
