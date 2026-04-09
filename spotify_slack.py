"""Spotify → Slack status updater."""

from enum import Enum

MAX_STATUS_LEN = 100
EMOJI = ":musical_note:"


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
