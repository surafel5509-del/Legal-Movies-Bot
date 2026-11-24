"""Run the official OpenCode web app with persistent state and Railway readiness."""
import base64
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time


def prepare():
    password = os.environ.get("OPENCODE_PASSWORD") or os.environ.get("OPENCODE_SERVER_PASSWORD", "")
    username = "opencode"  # OpenCode 2 uses a fixed Basic Auth username.
    if len(password) < 16:
        raise ValueError("Set OPENCODE_SERVER_PASSWORD to a unique password of at least 16 characters.")
    if any(c in username + password for c in "\r\n\x00"):
        raise ValueError("Invalid OpenCode authentication settings.")
    port = int(os.environ.get("PORT", "8080"))
    if not 1 <= port <= 65535 or port == 4096:
        raise ValueError("PORT must be between 1 and 65535, and different from the internal port 4096.")
    os.umask(0o077)
    paths = ["/data", "/data/home", "/data/workspace", "/data/xdg",
             "/data/xdg/data", "/data/xdg/config", "/data/xdg/state", "/data/xdg/cache"]
    for name in paths:
        path = Path(name)
        path.mkdir(parents=True, exist_ok=True)
        if os.geteuid() == 0:
            os.chown(path, 1000, 1000)
    os.environ.update(HOME="/data/home", XDG_DATA_HOME="/data/xdg/data",
                      XDG_CONFIG_HOME="/data/xdg/config", XDG_STATE_HOME="/data/xdg/state",
                      XDG_CACHE_HOME="/data/xdg/cache", OPENCODE_PASSWORD=password,
                      OPENCODE_SERVER_USERNAME=username, OPENCODE_SERVER_PASSWORD=password)
    auth = "Basic " + base64.b64encode((username + ":" + password).encode()).decode()
    proxy = {"handler": "reverse_proxy", "upstreams": [{"dial": "127.0.0.1:4096"}], "flush_interval": -1}
    health_proxy = dict(proxy, headers={"request": {"set": {"Authorization": [auth]}}})
    config = {"admin": {"disabled": True}, "logging": {"logs": {"default": {"level": "WARN"}}},
              "apps": {"http": {"servers": {"railway": {"listen": [":" + str(port)], "routes": [
                  {"match": [{"path": ["/healthz"], "method": ["GET", "HEAD"]}],
                   "handle": [{"handler": "rewrite", "uri": "/global/health"}, health_proxy], "terminal": True},
                  {"handle": [proxy], "terminal": True},
              ]}}}}}
    if os.geteuid() == 0:
        os.setgroups([])
        os.setgid(1000)
        os.setuid(1000)
    file = Path("/tmp/railway-caddy.json")
    file.write_text(json.dumps(config))
    file.chmod(0o600)
    return str(file)


def main():
    config = prepare()
    children = []
    stopping = False

    def stop(_signal=None, _frame=None):
        nonlocal stopping
        stopping = True
        for child in children:
            if child.poll() is None:
                child.terminate()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        children.append(subprocess.Popen(["opencode", "serve", "--hostname", "127.0.0.1", "--port", "4096"], cwd="/data/workspace"))
        children.append(subprocess.Popen(["caddy", "run", "--config", config]))
        print("OpenCode v2 web server starting. Workspace: /data/workspace; persistent state: /data/xdg", flush=True)
        while not stopping and all(p.poll() is None for p in children):
            time.sleep(0.25)
        result = 0 if stopping else next((p.returncode or 1 for p in children if p.poll() is not None), 1)
    finally:
        stop()
        deadline = time.monotonic() + 20
        for child in children:
            try:
                child.wait(timeout=max(0.1, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
    return result


if __name__ == "__main__":
    try:
        sys.exit(main())
    except ValueError as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
