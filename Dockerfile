FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends aria2 git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt ./
RUN python -m pip install --upgrade pip \
    && python -m pip install -r requirements.txt

COPY . .
RUN useradd --create-home --uid 10001 app \
    && mkdir -p /tmp/legal-movie-bot /app/data \
    && chown -R app:app /app /tmp/legal-movie-bot

USER app
EXPOSE 8080
CMD ["python", "-m", "bot.main"]
