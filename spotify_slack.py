"""Spotify → Slack status updater."""

MAX_STATUS_LEN = 100
EMOJI = ":musical_note:"


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
