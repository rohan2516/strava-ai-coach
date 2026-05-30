import requests
import os
import time
from typing import Optional
from pathlib import Path

# Load .env locally; on Streamlit Cloud, secrets come from st.secrets
try:
    from dotenv import load_dotenv, set_key
    load_dotenv()
    DOTENV_PATH = Path(__file__).parent / ".env"
    HAS_DOTENV = DOTENV_PATH.exists()
except ImportError:
    HAS_DOTENV = False

# Detect if running on Streamlit Cloud
def _get_secret(key: str, default: str = "") -> str:
    """Read from st.secrets (Streamlit Cloud) or os.environ (.env locally)."""
    try:
        import streamlit as st
        return st.secrets.get(key, os.getenv(key, default))
    except Exception:
        return os.getenv(key, default)


def _save_token_locally(access_token: str, refresh_token: str, expires_at: int):
    """Persist refreshed tokens back to .env (local only)."""
    if HAS_DOTENV:
        try:
            set_key(str(DOTENV_PATH), "STRAVA_ACCESS_TOKEN", access_token)
            set_key(str(DOTENV_PATH), "STRAVA_REFRESH_TOKEN", refresh_token)
            set_key(str(DOTENV_PATH), "STRAVA_TOKEN_EXPIRES_AT", str(expires_at))
        except Exception:
            pass  # Non-fatal if write fails


class StravaClient:
    """
    Lightweight Strava API v3 client with automatic token refresh.
    Works both locally (reads/writes .env) and on Streamlit Cloud
    (reads from st.secrets, stores refreshed tokens in st.session_state).
    """

    BASE_URL = "https://www.strava.com/api/v3"
    TOKEN_URL = "https://www.strava.com/oauth/token"

    def __init__(self, access_token: str):
        self.client_id = _get_secret("STRAVA_CLIENT_ID")
        self.client_secret = _get_secret("STRAVA_CLIENT_SECRET")
        self.refresh_token = _get_secret("STRAVA_REFRESH_TOKEN")
        self.token_expires_at = int(_get_secret("STRAVA_TOKEN_EXPIRES_AT", "0"))

        # On Streamlit Cloud, refreshed tokens live in session_state across reruns
        try:
            import streamlit as st
            if "strava_access_token" in st.session_state:
                self.access_token = st.session_state["strava_access_token"]
                self.refresh_token = st.session_state.get("strava_refresh_token", self.refresh_token)
                self.token_expires_at = st.session_state.get("strava_token_expires_at", self.token_expires_at)
            else:
                self.access_token = access_token
        except Exception:
            self.access_token = access_token

        self.session = requests.Session()
        self._set_auth_header(self.access_token)

    def _set_auth_header(self, token: str):
        self.session.headers.update({"Authorization": f"Bearer {token}"})

    def _is_token_expired(self) -> bool:
        """Returns True if token expires within the next 5 minutes."""
        return time.time() > (self.token_expires_at - 300)

    def _refresh_access_token(self):
        """
        Use the refresh token to get a new access token from Strava.
        - Locally: writes new tokens back to .env
        - Streamlit Cloud: stores in st.session_state (survives reruns)
        """
        if not self.client_id or not self.client_secret or not self.refresh_token:
            raise ValueError(
                "Cannot auto-refresh: STRAVA_CLIENT_ID, STRAVA_CLIENT_SECRET, "
                "and STRAVA_REFRESH_TOKEN must all be set in your secrets."
            )

        response = requests.post(self.TOKEN_URL, data={
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": self.refresh_token,
            "grant_type": "refresh_token",
        })
        response.raise_for_status()
        data = response.json()

        # Update in-memory values
        self.access_token = data["access_token"]
        self.refresh_token = data["refresh_token"]
        self.token_expires_at = data["expires_at"]

        # Persist to session_state (works on both local + cloud)
        try:
            import streamlit as st
            st.session_state["strava_access_token"] = self.access_token
            st.session_state["strava_refresh_token"] = self.refresh_token
            st.session_state["strava_token_expires_at"] = self.token_expires_at
        except Exception:
            pass

        # Also write back to .env if running locally
        _save_token_locally(self.access_token, self.refresh_token, self.token_expires_at)

        self._set_auth_header(self.access_token)

    def _ensure_valid_token(self):
        """Refresh token if expired or about to expire."""
        if self.refresh_token and self._is_token_expired():
            self._refresh_access_token()

    def _get(self, endpoint: str, params: dict = None) -> dict | list:
        self._ensure_valid_token()
        url = f"{self.BASE_URL}/{endpoint}"
        response = self.session.get(url, params=params or {})
        if response.status_code == 401:
            # Try one refresh on 401, then fail
            if self.refresh_token:
                self._refresh_access_token()
                response = self.session.get(url, params=params or {})
            if response.status_code == 401:
                raise ValueError(
                    "Strava authentication failed. Please re-run get_token.py "
                    "to generate a fresh token."
                )
        response.raise_for_status()
        return response.json()

    # ── Athlete ────────────────────────────────────────────────────────────────

    def get_athlete(self) -> dict:
        """Return the authenticated athlete's profile."""
        return self._get("athlete")

    def get_athlete_stats(self, athlete_id: int) -> dict:
        """Return aggregate stats for an athlete."""
        return self._get(f"athletes/{athlete_id}/stats")

    # ── Activities ─────────────────────────────────────────────────────────────

    def get_activities(self, limit: int = 30, before: Optional[int] = None,
                       after: Optional[int] = None) -> list[dict]:
        """
        Fetch recent activities.
        `before` / `after` are Unix timestamps (optional).
        Paginates automatically if limit > 30.
        """
        activities = []
        page = 1
        per_page = min(limit, 30)

        while len(activities) < limit:
            params = {"per_page": per_page, "page": page}
            if before:
                params["before"] = before
            if after:
                params["after"] = after

            batch = self._get("athlete/activities", params)
            if not batch:
                break

            activities.extend(batch)
            page += 1
            if len(batch) < per_page:
                break

        return activities[:limit]

    def get_activity_detail(self, activity_id: int) -> dict:
        """Return detailed info for a single activity (incl. segment efforts)."""
        return self._get(f"activities/{activity_id}")

    def get_activity_streams(self, activity_id: int,
                             stream_types: list[str] = None) -> dict:
        """Return time-series streams (heartrate, velocity, altitude, etc.)."""
        if stream_types is None:
            stream_types = ["time", "heartrate", "velocity_smooth", "altitude", "cadence"]
        keys = ",".join(stream_types)
        return self._get(f"activities/{activity_id}/streams",
                         {"keys": keys, "key_by_type": True})

    # ── Utility helpers ────────────────────────────────────────────────────────

    @staticmethod
    def format_activities_for_llm(activities: list[dict]) -> str:
        """
        Convert raw Strava activity list to a compact, human-readable text
        that works well as LLM context.
        """
        lines = ["=== STRAVA ACTIVITY LOG ===\n"]

        for act in activities:
            dist_km = act.get("distance", 0) / 1000
            time_sec = act.get("moving_time", 0)
            hours, rem = divmod(time_sec, 3600)
            minutes, seconds = divmod(rem, 60)
            duration_str = f"{hours}h {minutes}m {seconds}s" if hours else f"{minutes}m {seconds}s"

            avg_speed_kmh = act.get("average_speed", 0) * 3.6
            elev = act.get("total_elevation_gain", 0)
            hr = act.get("average_heartrate")
            max_hr = act.get("max_heartrate")
            calories = act.get("calories", act.get("kilojoules", 0))
            date = act.get("start_date_local", "")[:10]
            sport = act.get("sport_type", act.get("type", "Unknown"))
            kudos = act.get("kudos_count", 0)
            suffer = act.get("suffer_score")

            # Pace for running
            pace_str = ""
            if sport in ("Run", "VirtualRun") and avg_speed_kmh > 0:
                pace_sec_per_km = 3600 / avg_speed_kmh
                pace_min = int(pace_sec_per_km // 60)
                pace_sec = int(pace_sec_per_km % 60)
                pace_str = f" | Pace: {pace_min}:{pace_sec:02d}/km"

            line = (
                f"[{date}] {sport}: \"{act.get('name', 'Untitled')}\" | "
                f"Distance: {dist_km:.2f} km | Duration: {duration_str} | "
                f"Avg speed: {avg_speed_kmh:.1f} km/h{pace_str} | "
                f"Elevation: {elev:.0f}m"
            )
            if hr:
                line += f" | Avg HR: {hr:.0f} bpm"
            if max_hr:
                line += f" | Max HR: {max_hr:.0f} bpm"
            if calories:
                line += f" | Calories: {calories:.0f}"
            if suffer:
                line += f" | Suffer score: {suffer}"
            if kudos:
                line += f" | Kudos: {kudos}"

            lines.append(line)

        return "\n".join(lines)

    @staticmethod
    def format_athlete_for_llm(athlete: dict) -> str:
        """Compact athlete profile for LLM context."""
        if not athlete:
            return ""
        parts = [
            f"Athlete: {athlete.get('firstname', '')} {athlete.get('lastname', '')}",
            f"Location: {athlete.get('city', 'Unknown')}, {athlete.get('country', '')}",
            f"Following: {athlete.get('friend_count', 0)} | Followers: {athlete.get('follower_count', 0)}",
            f"Weight: {athlete.get('weight', 'N/A')} kg",
            f"FTP: {athlete.get('ftp', 'N/A')} W",
        ]
        return " | ".join(p for p in parts if "N/A" not in p and "Unknown" not in p)