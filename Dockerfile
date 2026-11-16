FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends aria2 git ca-certificates gosu \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt ./
RUN python -m pip install --upgrade pip \
    && python -m pip install -r requirements.txt

COPY . .
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN useradd --create-home --uid 10001 app \
    && mkdir -p /tmp/legal-movie-bot /app/data /data \
    && chown -R app:app /app /tmp/legal-movie-bot \
    && chmod 755 /usr/local/bin/docker-entrypoint.sh

USER root
EXPOSE 8080
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD ["python", "-m", "bot.main"]
