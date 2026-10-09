# Playwright base already ships Chromium + all system deps browser-use needs.
FROM mcr.microsoft.com/playwright/python:v1.47.0-jammy

WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# browser-use 0.13 drives Chromium via CDP; make sure a chromium binary is present
# (the base image has one; this is belt-and-braces and a no-op if already installed)
RUN python -m playwright install chromium >/dev/null 2>&1 || true

COPY app.py .
ENV PYTHONUNBUFFERED=1
EXPOSE 8600
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8600"]
