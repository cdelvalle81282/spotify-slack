from spotify_slack import format_status


def _track(name, artists):
    return {"name": name, "artists": [{"name": a} for a in artists]}


def test_format_status_single_artist():
    text, emoji = format_status(_track("Bohemian Rhapsody", ["Queen"]))
    assert text == "Bohemian Rhapsody — Queen"
    assert emoji == ":musical_note:"


def test_format_status_multiple_artists():
    text, _ = format_status(_track("Under Pressure", ["Queen", "David Bowie"]))
    assert text == "Under Pressure — Queen, David Bowie"


def test_format_status_unicode():
    text, _ = format_status(_track("Café del Mar", ["Energy 52"]))
    assert text == "Café del Mar — Energy 52"


def test_format_status_truncates_to_100_chars():
    long_name = "A" * 120
    text, _ = format_status(_track(long_name, ["B"]))
    assert len(text) == 100
    assert text.endswith("…")


def test_format_status_handles_missing_artists():
    text, _ = format_status({"name": "Unknown", "artists": []})
    assert text == "Unknown"


from spotify_slack import Action, decide_action


def test_decide_action_new_track():
    action = decide_action(current_id="abc", last_id=None, is_playing=True, last_cleared=False)
    assert action == Action.UPDATE


def test_decide_action_same_track():
    action = decide_action(current_id="abc", last_id="abc", is_playing=True, last_cleared=False)
    assert action == Action.SKIP


def test_decide_action_switched_track():
    action = decide_action(current_id="xyz", last_id="abc", is_playing=True, last_cleared=False)
    assert action == Action.UPDATE


def test_decide_action_stopped_not_cleared():
    action = decide_action(current_id=None, last_id="abc", is_playing=False, last_cleared=False)
    assert action == Action.CLEAR


def test_decide_action_stopped_already_cleared():
    action = decide_action(current_id=None, last_id=None, is_playing=False, last_cleared=True)
    assert action == Action.SKIP


from spotify_slack import build_slack_profile, build_clear_profile


def test_build_slack_profile_basic():
    profile = build_slack_profile("Song — Artist", ":musical_note:")
    assert profile == {
        "status_text": "Song — Artist",
        "status_emoji": ":musical_note:",
        "status_expiration": 0,
    }


def test_build_clear_profile():
    profile = build_clear_profile()
    assert profile == {"status_text": "", "status_emoji": ""}


import pytest
from spotify_slack import Config, load_config, ConfigError


def test_load_config_reads_env(monkeypatch):
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "cid")
    monkeypatch.setenv("SPOTIFY_CLIENT_SECRET", "csecret")
    monkeypatch.setenv("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8888/callback")
    monkeypatch.setenv("SLACK_USER_TOKEN", "xoxp-test")
    cfg = load_config()
    assert cfg == Config(
        spotify_client_id="cid",
        spotify_client_secret="csecret",
        spotify_redirect_uri="http://127.0.0.1:8888/callback",
        slack_user_token="xoxp-test",
    )


def test_load_config_raises_on_missing(monkeypatch):
    for var in ("SPOTIFY_CLIENT_ID", "SPOTIFY_CLIENT_SECRET", "SLACK_USER_TOKEN"):
        monkeypatch.delenv(var, raising=False)
    with pytest.raises(ConfigError):
        load_config()


def test_config_repr_redacts_secrets():
    cfg = Config(
        spotify_client_id="real_client_id",
        spotify_client_secret="real_client_secret",
        spotify_redirect_uri="http://127.0.0.1:8888/callback",
        slack_user_token="xoxp-real-token",
    )
    rendered = repr(cfg)
    assert "real_client_id" not in rendered
    assert "real_client_secret" not in rendered
    assert "xoxp-real-token" not in rendered
    assert "<redacted>" in rendered
    assert "http://127.0.0.1:8888/callback" in rendered
