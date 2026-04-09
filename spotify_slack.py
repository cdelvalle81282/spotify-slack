"""Spotify → Slack status updater."""

from dataclasses import dataclass
from enum import Enum

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

MAX_STATUS_LEN = 100
EMOJI = ":musical_note:"
LOG_PATH = Path(__file__).parent / "spotify_slack.log"


class Action(Enum):
    UPDATE = "update"
    CLEAR = "clear"
    SKIP = "skip"


def decide_action(*, current_id, last_id, is_playing, last_cleared):
    """Decide whether to update, clear, or skip the Slack status."""
    if not is_playing or current_id is None:
        return Action.SKIP if last_cleared else Action.CLEAR
    if current_id == last_id:
        return Action.SKIP
    return Action.UPDATE


def format_status(track):
    """Turn a Spotify track dict into (status_text, status_emoji)."""
    name = track.get("name", "")
    artists = [a["name"] for a in track.get("artists", []) if a.get("name")]
    if artists:
        text = f"{name} — {', '.join(artists)}"
    else:
        text = name
    if len(text) > MAX_STATUS_LEN:
        text = text[: MAX_STATUS_LEN - 1] + "…"
    return text, EMOJI


def build_slack_profile(status_text, status_emoji):
    return {
        "status_text": status_text,
        "status_emoji": status_emoji,
        "status_expiration": 0,
    }


def build_clear_profile():
    return {"status_text": "", "status_emoji": ""}


class ConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class Config:
    spotify_client_id: str
    spotify_client_secret: str
    spotify_redirect_uri: str
    slack_user_token: str

    def __repr__(self):
        return (
            "Config(spotify_client_id=<redacted>, "
            "spotify_client_secret=<redacted>, "
            f"spotify_redirect_uri={self.spotify_redirect_uri!r}, "
            "slack_user_token=<redacted>)"
        )


def load_config():
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
    required = {
        "SPOTIFY_CLIENT_ID": os.environ.get("SPOTIFY_CLIENT_ID"),
        "SPOTIFY_CLIENT_SECRET": os.environ.get("SPOTIFY_CLIENT_SECRET"),
        "SLACK_USER_TOKEN": os.environ.get("SLACK_USER_TOKEN"),
    }
    missing = [k for k, v in required.items() if not v]
    if missing:
        raise ConfigError(f"Missing required env vars: {', '.join(missing)}")
    return Config(
        spotify_client_id=required["SPOTIFY_CLIENT_ID"],
        spotify_client_secret=required["SPOTIFY_CLIENT_SECRET"],
        spotify_redirect_uri=os.environ.get(
            "SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8888/callback"
        ),
        slack_user_token=required["SLACK_USER_TOKEN"],
    )


def configure_logging():
    level = logging.DEBUG if os.environ.get("SPOTIFY_SLACK_DEBUG") == "1" else logging.INFO
    handler = RotatingFileHandler(LOG_PATH, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()
    root.addHandler(handler)
    # Also log to stderr when running interactively
    stream = logging.StreamHandler()
    stream.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    root.addHandler(stream)
    return logging.getLogger("spotify_slack")
