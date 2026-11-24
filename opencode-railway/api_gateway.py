"""Authenticated, narrow API gateway for the Android client."""
import base64
import hashlib
import hmac
import json
import os
import re
import threading
import time
from collections import defaultdict, deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlsplit
from urllib.request import Request, urlopen

HOST = "127.0.0.1"
PORT = 4097
UPSTREAM = "http://127.0.0.1:4096"
LOGIN_USER = os.environ.get("APP_LOGIN_USERNAME", "")
LOGIN_PASSWORD = os.environ.get("APP_LOGIN_PASSWORD", "")
JWT_SECRET = os.environ.get("APP_JWT_SECRET", "")
JWT_TTL = min(max(int(os.environ.get("APP_JWT_TTL_SECONDS", "604800")), 900), 2592000)
MAX_BODY = 1024 * 1024
SESSION_ID = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
login_attempts = defaultdict(deque)
attempt_lock = threading.Lock()


def b64u(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def token_issue(subject):
    now = int(time.time())
    head = b64u(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    body = b64u(json.dumps({"sub": subject, "iat": now, "exp": now + JWT_TTL, "iss": "opencode-android-api"}, separators=(",", ":")).encode())
    unsigned = head + "." + body
    sig = b64u(hmac.new(JWT_SECRET.encode(), unsigned.encode(), hashlib.sha256).digest())
    return unsigned + "." + sig


def token_valid(value):
    try:
        head, body, signature = value.split(".")
        unsigned = head + "." + body
        expected = b64u(hmac.new(JWT_SECRET.encode(), unsigned.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected):
            return False
        payload = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
        return payload.get("iss") == "opencode-android-api" and payload.get("sub") == LOGIN_USER and int(payload.get("exp", 0)) > int(time.time())
    except Exception:
        return False


def upstream(method, path, body=None, timeout=90):
    password = os.environ.get("OPENCODE_SERVER_PASSWORD") or os.environ.get("OPENCODE_PASSWORD", "")
    if not password:
        raise RuntimeError("OpenCode server password is not configured")
    auth = base64.b64encode(("opencode:" + password).encode()).decode()
    data = None if body is None else json.dumps(body).encode()
    req = Request(UPSTREAM + path, data=data, method=method, headers={
        "Authorization": "Basic " + auth,
        "Accept": "application/json",
        "Content-Type": "application/json",
    })
    try:
        with urlopen(req, timeout=timeout) as response:
            raw = response.read(MAX_BODY * 8)
            return response.status, response.headers.get("Content-Type", "application/json"), raw
    except HTTPError as error:
        return error.code, error.headers.get("Content-Type", "application/json"), error.read(MAX_BODY * 8)
    except URLError as error:
        raise RuntimeError("OpenCode server is temporarily unavailable") from error


class Handler(BaseHTTPRequestHandler):
    server_version = "AgentAPI/1.0"

    def log_message(self, fmt, *args):
        # Do not log authorization headers or request bodies.
        print("AgentAPI " + (fmt % args), flush=True)

    def send_json(self, status, payload):
        data = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.end_headers()
        self.wfile.write(data)

    def send_upstream(self, status, content_type, raw):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.end_headers()
        if raw:
            self.wfile.write(raw)

    def read_json(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            raise ValueError("Invalid Content-Length")
        if length < 0 or length > MAX_BODY:
            raise ValueError("Request body is too large")
        raw = self.rfile.read(length)
        try:
            obj = json.loads(raw or b"{}")
        except json.JSONDecodeError:
            raise ValueError("Request body must be valid JSON")
        if not isinstance(obj, dict):
            raise ValueError("JSON body must be an object")
        return obj

    def authorized(self):
        header = self.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            return False
        return token_valid(header[7:].strip())

    def do_OPTIONS(self):
        self.send_json(204, {})

    def do_GET(self):
        parsed = urlsplit(self.path)
        path = parsed.path
        if path == "/v1/health":
            try:
                status, _, raw = upstream("GET", "/api/info", timeout=8)
                self.send_json(200 if status == 200 else 503, {"status": "ok" if status == 200 else "degraded", "opencode": status == 200, "api": "v1"})
            except Exception:
                self.send_json(503, {"status": "degraded", "opencode": False, "api": "v1"})
            return
        if not self.authorized():
            self.send_json(401, {"error": "unauthorized", "message": "Sign in to obtain an access token"})
            return
        query = parse_qs(parsed.query, keep_blank_values=False)
        try:
            if path == "/v1/sessions":
                params = {k: query[k][0] for k in ("limit", "order", "search", "archived", "cursor") if k in query}
                suffix = "?" + urlencode(params) if params else ""
                self.proxy("GET", "/api/session" + suffix)
                return
            if path == "/v1/agents":
                self.proxy("GET", "/api/agent")
                return
            if path == "/v1/providers":
                self.proxy("GET", "/api/provider")
                return
            match = re.fullmatch(r"/v1/sessions/([^/]+)", path)
            if match and SESSION_ID.fullmatch(match.group(1)):
                self.proxy("GET", "/api/session/" + match.group(1))
                return
            match = re.fullmatch(r"/v1/sessions/([^/]+)/messages", path)
            if match and SESSION_ID.fullmatch(match.group(1)):
                params = {k: query[k][0] for k in ("limit", "order", "cursor", "type") if k in query}
                suffix = "?" + urlencode(params) if params else ""
                self.proxy("GET", "/api/session/" + match.group(1) + "/message" + suffix)
                return
            self.send_json(404, {"error": "not_found"})
        except Exception as error:
            self.send_json(502, {"error": "upstream_error", "message": str(error)})

    def do_POST(self):
        parsed = urlsplit(self.path)
        path = parsed.path
        try:
            body = self.read_json()
        except ValueError as error:
            self.send_json(400, {"error": "bad_request", "message": str(error)})
            return
        if path == "/v1/auth/login":
            now = time.time()
            client = self.client_address[0]
            with attempt_lock:
                attempts = login_attempts[client]
                while attempts and attempts[0] < now - 300:
                    attempts.popleft()
                if len(attempts) >= 5:
                    self.send_json(429, {"error": "rate_limited", "message": "Too many login attempts. Try again in five minutes."})
                    return
                attempts.append(now)
            username = str(body.get("username", ""))
            password = str(body.get("password", ""))
            if not LOGIN_USER or not LOGIN_PASSWORD or not JWT_SECRET:
                self.send_json(503, {"error": "auth_not_configured"})
                return
            if not (hmac.compare_digest(username, LOGIN_USER) and hmac.compare_digest(password, LOGIN_PASSWORD)):
                self.send_json(401, {"error": "invalid_credentials"})
                return
            with attempt_lock:
                login_attempts.pop(client, None)
            self.send_json(200, {"access_token": token_issue(LOGIN_USER), "token_type": "Bearer", "expires_in": JWT_TTL})
            return
        if not self.authorized():
            self.send_json(401, {"error": "unauthorized"})
            return
        try:
            if path == "/v1/sessions":
                payload = {}
                if "title" in body:
                    payload["title"] = str(body["title"])[:160]
                self.proxy("POST", "/api/session", payload)
                return
            match = re.fullmatch(r"/v1/sessions/([^/]+)/messages", path)
            if match and SESSION_ID.fullmatch(match.group(1)):
                message = body.get("message")
                if not isinstance(message, str) or not message.strip() or len(message) > 50000:
                    self.send_json(400, {"error": "invalid_message", "message": "message must be 1-50000 characters"})
                    return
                payload = {"parts": [{"type": "text", "text": message}]}
                agent = body.get("agent")
                if isinstance(agent, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,80}", agent):
                    payload["agent"] = agent
                model = body.get("model")
                if isinstance(model, dict) and isinstance(model.get("providerID"), str) and isinstance(model.get("id"), str):
                    payload["model"] = {"providerID": model["providerID"], "id": model["id"]}
                self.proxy("POST", "/api/session/" + match.group(1) + "/prompt", payload, timeout=120)
                return
            match = re.fullmatch(r"/v1/sessions/([^/]+)/interrupt", path)
            if match and SESSION_ID.fullmatch(match.group(1)):
                self.proxy("POST", "/api/session/" + match.group(1) + "/interrupt", {})
                return
            self.send_json(404, {"error": "not_found"})
        except Exception as error:
            self.send_json(502, {"error": "upstream_error", "message": str(error)})

    def do_DELETE(self):
        path = urlsplit(self.path).path
        if not self.authorized():
            self.send_json(401, {"error": "unauthorized"})
            return
        match = re.fullmatch(r"/v1/sessions/([^/]+)", path)
        if match and SESSION_ID.fullmatch(match.group(1)):
            try:
                self.proxy("DELETE", "/api/session/" + match.group(1))
            except Exception as error:
                self.send_json(502, {"error": "upstream_error", "message": str(error)})
            return
        self.send_json(404, {"error": "not_found"})

    def proxy(self, method, path, body=None, timeout=90):
        status, content_type, raw = upstream(method, path, body, timeout=timeout)
        self.send_upstream(status, content_type, raw)


def main():
    if not LOGIN_USER or len(LOGIN_PASSWORD) < 16 or len(JWT_SECRET) < 32:
        raise RuntimeError("APP_LOGIN_USERNAME, APP_LOGIN_PASSWORD (16+ chars), and APP_JWT_SECRET (32+ chars) are required")
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    server.daemon_threads = True
    print("Authenticated Android API listening on 127.0.0.1:4097", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
