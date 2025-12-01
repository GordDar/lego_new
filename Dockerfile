FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    chromium \
    chromium-driver \
    curl \
    unzip \
    libglib2.0-0 \
    libnss3 \
    libfontconfig1 \
    libxss1 \
    libx11-xcb1 \
    libgtk-3-0 \
    libdbus-glib-1-2 \
    libxtst6 \
    --no-install-recommends && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

ENV CHROMEDRIVER_PATH=/usr/lib/chromium/chromedriver
ENV PATH="${CHROMEDRIVER_PATH}:${PATH}"
ENV FLASK_APP="app_lego:app"

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install gunicorn

COPY . .

COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

EXPOSE 8080

# ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["python", "-m", "flask", "run", "--port=8080"]
