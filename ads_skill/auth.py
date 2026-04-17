"""OAuth2 flow and token lifecycle management for Google Ads."""

import json
import sys
import threading
import time
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request as URLRequest
from urllib.request import urlopen

from .config import (
    CLIENT_ID,
    CLIENT_SECRET,
    REDIRECT_URI,
    SCOPES,
    load_tokens,
    save_tokens,
)

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_REVOKE_URL = "https://oauth2.googleapis.com/revoke"


class _CallbackHandler(BaseHTTPRequestHandler):
    auth_code: str | None = None
    error: str | None = None

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/callback":
            params = parse_qs(parsed.query)
            if "code" in params:
                _CallbackHandler.auth_code = params["code"][0]
                body = b"""
                <html><body style="font-family:sans-serif;padding:2em;text-align:center">
                <h2>Authorization successful</h2>
                <p>You can close this tab and return to the terminal.</p>
                </body></html>"""
            else:
                _CallbackHandler.error = params.get("error", ["unknown"])[0]
                body = b"<html><body><h2>Authorization failed</h2></body></html>"

            code = 200 if "code" in params else 400
            self.send_response(code)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(204)
            self.end_headers()

    def log_message(self, *args) -> None:  # silence request logs
        pass


def _build_auth_url() -> str:
    params = {
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "prompt": "consent",  # force consent screen to always get refresh_token
    }
    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"


def _post(url: str, data: dict) -> dict:
    encoded = urllib.parse.urlencode(data).encode()
    req = URLRequest(url, data=encoded, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    with urlopen(req) as resp:
        return json.loads(resp.read())


def login() -> None:
    """Run the full OAuth2 authorization code flow on port 8086."""
    auth_url = _build_auth_url()

    _CallbackHandler.auth_code = None
    _CallbackHandler.error = None

    server = HTTPServer(("localhost", 8086), _CallbackHandler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()

    print(f"\nOpening browser for Google authorization...")
    print(f"If the browser doesn't open, visit:\n{auth_url}\n")
    webbrowser.open(auth_url)

    timeout = 120
    start = time.monotonic()
    try:
        while _CallbackHandler.auth_code is None and _CallbackHandler.error is None:
            if time.monotonic() - start > timeout:
                print("Timeout waiting for authorization (2 min).")
                sys.exit(1)
            time.sleep(0.3)
    finally:
        server.shutdown()

    if _CallbackHandler.error:
        print(f"Authorization failed: {_CallbackHandler.error}")
        sys.exit(1)

    print("Got authorization code — exchanging for tokens...")
    tokens = _post(
        GOOGLE_TOKEN_URL,
        {
            "code": _CallbackHandler.auth_code,
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "redirect_uri": REDIRECT_URI,
            "grant_type": "authorization_code",
        },
    )

    if "refresh_token" not in tokens:
        print(
            "No refresh token returned. You may need to revoke access at "
            "https://myaccount.google.com/permissions and try again."
        )
        sys.exit(1)

    tokens["created_at"] = time.time()
    save_tokens(tokens)
    print("Login successful. Credentials saved to ~/.ads-skill/tokens.json")


def refresh(force: bool = False) -> str | None:
    """Return a valid access token, refreshing from Google if needed.

    Returns None if not authenticated.
    """
    tokens = load_tokens()
    if not tokens:
        return None

    created_at = tokens.get("created_at", 0)
    expires_in = tokens.get("expires_in", 3600)
    # Treat token as expired 60 s early to avoid race conditions
    if not force and time.time() < created_at + expires_in - 60:
        return tokens["access_token"]

    refresh_token = tokens.get("refresh_token")
    if not refresh_token:
        return None

    new = _post(
        GOOGLE_TOKEN_URL,
        {
            "refresh_token": refresh_token,
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "grant_type": "refresh_token",
        },
    )
    new["refresh_token"] = refresh_token  # Google only sends it on first exchange
    new["created_at"] = time.time()
    save_tokens(new)
    return new["access_token"]


def status() -> dict:
    """Return a dict describing current auth state (no network calls)."""
    tokens = load_tokens()
    if not tokens:
        return {"logged_in": False}

    created_at = tokens.get("created_at", 0)
    expires_in = tokens.get("expires_in", 3600)
    expires_at = created_at + expires_in

    return {
        "logged_in": True,
        "has_refresh_token": bool(tokens.get("refresh_token")),
        "expires_at": expires_at,
        "expired": time.time() > expires_at - 60,
        "remaining": max(0, int(expires_at - time.time())),
    }
