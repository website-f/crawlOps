# Playwright base already has all Firefox/Chromium system deps installed.
FROM mcr.microsoft.com/playwright/python:v1.47.0-jammy

WORKDIR /srv
RUN pip install --no-cache-dir "camoufox[geoip]" fastapi "uvicorn[standard]"
# download the Camoufox anti-detect browser build at image-build time
RUN python -m camoufox fetch

COPY app.py .
ENV PYTHONUNBUFFERED=1
EXPOSE 8500
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8500"]
