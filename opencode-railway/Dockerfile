FROM caddy:2.11.7-alpine@sha256:d8542f48d34a9cf4e4c11a478865229840e87e4c96ea3f439101f31a5d35f75f AS caddy
FROM node:24-bookworm-slim@sha256:a5f4366e834695d5f363b920c104953a535d3a9864d1bdf74566a0ebe01daee5

RUN apt-get update && apt-get install -y --no-install-recommends \
    bash ca-certificates curl git openssh-client python3 ripgrep tini libstdc++6 \
    && rm -rf /var/lib/apt/lists/* \
    && curl --fail --location --retry 3 https://github.com/anomalyco/opencode/releases/download/v2.3.2/opencode-linux-x64-baseline.tar.gz -o /tmp/opencode.tar.gz \
    && echo '563b5d663637226b6e3bb4bb6803281bc39b0d2cd88db06d674b6420aab009b0  /tmp/opencode.tar.gz' | sha256sum -c - \
    && tar -xzf /tmp/opencode.tar.gz -C /usr/local/bin opencode \
    && chmod 755 /usr/local/bin/opencode && rm /tmp/opencode.tar.gz \
    && opencode --version

COPY --from=caddy /usr/bin/caddy /usr/bin/caddy
COPY entrypoint.py /opt/railway/entrypoint.py
RUN mkdir -p /etc/opencode
COPY opencode.json /etc/opencode/opencode.json

ENV PORT=8080 HOME=/data/home \
    XDG_DATA_HOME=/data/xdg/data XDG_CONFIG_HOME=/data/xdg/config \
    XDG_STATE_HOME=/data/xdg/state XDG_CACHE_HOME=/data/xdg/cache \
    OPENCODE_SERVER_USERNAME=opencode OPENCODE_DISABLE_AUTOUPDATE=true \
    BUN_RUNTIME_TRANSPILER_CACHE_PATH=0

WORKDIR /data/workspace
EXPOSE 8080
ENTRYPOINT ["/usr/bin/tini", "-s", "-g", "--", "python3", "-u", "/opt/railway/entrypoint.py"]
