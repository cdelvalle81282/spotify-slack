"""Spotify → Slack status updater."""

from dataclasses import dataclass
from enum import Enum

import logging
import os
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path

MAX_STATUS_LEN = 100
EMOJI = ":musical_note:"
LOG_PATH = Path(__file__).parent / "spotify_slack.log"
SPOTIFY_SCOPE = "user-read-currently-playing"
SPOTIFY_CACHE_PATH = Path(__file__).parent / ".spotify_cache"
POLL_INTERVAL_SECONDS = 60

log = logging.getLogger("spotify_slack")


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


@dataclass(frozen=True)
class State:
    last_track_id: str | None = None
    last_cleared: bool = False


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


def make_spotify_client(cfg):
    from spotipy import Spotify
    from spotipy.oauth2 import SpotifyOAuth

    auth = SpotifyOAuth(
        client_id=cfg.spotify_client_id,
        client_secret=cfg.spotify_client_secret,
        redirect_uri=cfg.spotify_redirect_uri,
        scope=SPOTIFY_SCOPE,
        cache_path=str(SPOTIFY_CACHE_PATH),
        open_browser=True,
    )
    return Spotify(auth_manager=auth)


def make_slack_client(cfg):
    from slack_sdk import WebClient
    return WebClient(token=cfg.slack_user_token)


def poll_once(spotify_client, slack_client, state):
    """Run one iteration of the polling loop. Returns the new state."""
    current = spotify_client.current_user_playing_track()
    current_id = None
    is_playing = False
    if current and current.get("is_playing") and current.get("item"):
        current_id = current["item"]["id"]
        is_playing = True

    action = decide_action(
        current_id=current_id,
        last_id=state.last_track_id,
        is_playing=is_playing,
        last_cleared=state.last_cleared,
    )

    if action == Action.UPDATE:
        text, emoji = format_status(current["item"])
        slack_client.users_profile_set(profile=build_slack_profile(text, emoji))
        log.info("status updated: %s", text)
        return State(last_track_id=current_id, last_cleared=False)

    if action == Action.CLEAR:
        slack_client.users_profile_set(profile=build_clear_profile())
        log.info("status cleared")
        return State(last_track_id=None, last_cleared=True)

    return state


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


def run_forever():
    configure_logging()
    log.info("starting spotify_slack")
    cfg = load_config()
    spotify = make_spotify_client(cfg)
    slack = make_slack_client(cfg)
    state = State()

    try:
        while True:
            try:
                state = poll_once(spotify, slack, state)
            except Exception:
                log.exception("error in poll iteration; continuing")
            time.sleep(POLL_INTERVAL_SECONDS)
    except KeyboardInterrupt:
        log.info("shutting down on KeyboardInterrupt")


if __name__ == "__main__":
    run_forever()
