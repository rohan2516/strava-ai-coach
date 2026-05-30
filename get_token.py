"""
Helper script to get a Strava access token via OAuth.
Run: python get_token.py
Automatically saves all tokens to your .env file.
"""
import webbrowser
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from dotenv import set_key
from pathlib import Path
import os

DOTENV_PATH = Path(__file__).parent / ".env"

CLIENT_ID = os.getenv("STRAVA_CLIENT_ID") or input("Enter your Strava Client ID: ")
CLIENT_SECRET = os.getenv("STRAVA_CLIENT_SECRET") or input("Enter your Strava Client Secret: ")

auth_code = None


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        global auth_code
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        if "code" in params:
            auth_code = params["code"][0]
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"<h2>Success! You can close this tab.</h2>")
        else:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"<h2>Error: no code received.</h2>")

    def log_message(self, format, *args):
        pass  # suppress server logs


REDIRECT_URI = "http://localhost:8080"
auth_url = (
    f"https://www.strava.com/oauth/authorize"
    f"?client_id={CLIENT_ID}"
    f"&redirect_uri={REDIRECT_URI}"
    f"&response_type=code"
    f"&scope=read,activity:read_all"
)

print(f"\n🔗 Opening Strava authorization page...")
print(f"If it doesn't open, visit:\n{auth_url}\n")
webbrowser.open(auth_url)

server = HTTPServer(("localhost", 8080), Handler)
print("⏳ Waiting for OAuth callback on http://localhost:8080 ...")
server.handle_request()

if auth_code:
    print(f"\n✅ Authorization code received. Exchanging for token...")
    resp = requests.post("https://www.strava.com/oauth/token", data={
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "code": auth_code,
        "grant_type": "authorization_code",
    })
    data = resp.json()

    if "access_token" in data:
        # Save everything to .env automatically
        set_key(str(DOTENV_PATH), "STRAVA_CLIENT_ID", CLIENT_ID)
        set_key(str(DOTENV_PATH), "STRAVA_CLIENT_SECRET", CLIENT_SECRET)
        set_key(str(DOTENV_PATH), "STRAVA_ACCESS_TOKEN", data["access_token"])
        set_key(str(DOTENV_PATH), "STRAVA_REFRESH_TOKEN", data["refresh_token"])
        set_key(str(DOTENV_PATH), "STRAVA_TOKEN_EXPIRES_AT", str(data["expires_at"]))

        print(f"\n🎉 All tokens saved to .env automatically!")
        print(f"   Access Token:  {data['access_token'][:20]}...")
        print(f"   Refresh Token: {data['refresh_token'][:20]}...")
        print(f"\nYou're all set — the app will auto-refresh tokens from now on.")
    else:
        print(f"\n❌ Error: {data}")
else:
    print("❌ No authorization code received.")