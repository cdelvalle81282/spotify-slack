# Spotify → Slack Status Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** A background Python script that polls Spotify every 60 seconds and updates the user's Slack status with the currently playing track, clearing the status when playback stops. Runs at Windows logon.

**Architecture:** Single-file polling loop using `spotipy` (Spotify) and `slack_sdk` (Slack). OAuth refresh handled by `spotipy`'s built-in cache. In-memory state tracks the last-seen track ID to avoid redundant Slack calls. Run at logon via a Startup folder shortcut to `run.bat`.

**Tech Stack:** Python 3.10+, `spotipy`, `slack_sdk`, `python-dotenv`, `pytest`.

**Reference design:** `docs/plans/2026-04-09-spotify-slack-status-design.md`

---

## Task 0: Project scaffolding

**Files:**
- Create: `C:\Users\charl\Documents\SpotifySlack\.gitignore`
- Create: `C:\Users\charl\Documents\SpotifySlack\requirements.txt`
- Create: `C:\Users\charl\Documents\SpotifySlack\.env.example`
- Create: `C:\Users\charl\Documents\SpotifySlack\README.md`

**Step 1: Initialize git repo**

Run: `cd C:/Users/charl/Documents/SpotifySlack && git init`
Expected: `Initialized empty Git repository in ...`

**Step 2: Create `.gitignore`**

```
# Python
__pycache__/
*.py[cod]
.venv/
venv/
*.egg-info/

# Secrets & state
.env
.spotify_cache
spotify_slack.log
spotify_slack.log.*

# IDE
.vscode/
.idea/
```

**Step 3: Create `requirements.txt`**

```
spotipy>=2.23,<3
slack_sdk>=3.27,<4
python-dotenv>=1.0,<2
pytest>=8.0,<9
```

**Step 4: Create `.env.example`**

```
SPOTIFY_CLIENT_ID=
SPOTIFY_CLIENT_SECRET=
SPOTIFY_REDIRECT_URI=http://127.0.0.1:8888/callback
SLACK_USER_TOKEN=
# Optional: set to 1 to enable DEBUG logging
SPOTIFY_SLACK_DEBUG=0
```

**Step 5: Create `README.md` with setup walkthrough**

Copy the "Setup walkthrough" section from `docs/plans/2026-04-09-spotify-slack-status-design.md` into `README.md`. Add a short "What this does" paragraph at the top.

**Step 6: Create virtualenv and install dependencies**

Run:
```
cd C:/Users/charl/Documents/SpotifySlack
python -m venv .venv
.venv/Scripts/python -m pip install --upgrade pip
.venv/Scripts/python -m pip install -r requirements.txt
```
Expected: `Successfully installed spotipy-... slack_sdk-... python-dotenv-... pytest-...`

**Step 7: Commit**

```bash
git add .gitignore requirements.txt .env.example README.md docs/
git commit -m "chore: scaffold project with deps, env template, and design docs"
```

---

## Task 1: `format_status` pure function

**Files:**
- Create: `C:\Users\charl\Documents\SpotifySlack\spotify_slack.py`
- Create: `C:\Users\charl\Documents\SpotifySlack\tests\__init__.py` (empty)
- Create: `C:\Users\charl\Documents\SpotifySlack\tests\test_spotify_slack.py`

**Step 1: Write the failing tests**

Create `tests/test_spotify_slack.py`:

```python
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
```

**Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_spotify_slack.py -v`
Expected: `ModuleNotFoundError: No module named 'spotify_slack'` or similar.

**Step 3: Create minimal `spotify_slack.py` with `format_status`**

```python
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
```

**Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_spotify_slack.py -v`
Expected: `5 passed`

**Step 5: Commit**

```bash
git add spotify_slack.py tests/__init__.py tests/test_spotify_slack.py
git commit -m "feat: add format_status helper with truncation and tests"
```

---

## Task 2: `should_update` decision function

**Files:**
- Modify: `C:\Users\charl\Documents\SpotifySlack\spotify_slack.py`
- Modify: `C:\Users\charl\Documents\SpotifySlack\tests\test_spotify_slack.py`

**Step 1: Write the failing tests**

Append to `tests/test_spotify_slack.py`:

```python
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
```

**Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_spotify_slack.py -v`
Expected: `ImportError: cannot import name 'Action'` or similar.

**Step 3: Add `Action` enum and `decide_action` to `spotify_slack.py`**

Add near the top, below the existing constants:

```python
from enum import Enum


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
```

**Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_spotify_slack.py -v`
Expected: `10 passed`

**Step 5: Commit**

```bash
git add spotify_slack.py tests/test_spotify_slack.py
git commit -m "feat: add decide_action state machine with tests"
```

---

## Task 3: `build_slack_profile` helper

**Files:**
- Modify: `C:\Users\charl\Documents\SpotifySlack\spotify_slack.py`
- Modify: `C:\Users\charl\Documents\SpotifySlack\tests\test_spotify_slack.py`

**Step 1: Write the failing tests**

Append to `tests/test_spotify_slack.py`:

```python
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
```

**Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_spotify_slack.py -v`
Expected: `ImportError: cannot import name 'build_slack_profile'`

**Step 3: Add helpers to `spotify_slack.py`**

```python
def build_slack_profile(status_text, status_emoji):
    return {
        "status_text": status_text,
        "status_emoji": status_emoji,
        "status_expiration": 0,
    }


def build_clear_profile():
    return {"status_text": "", "status_emoji": ""}
```

**Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_spotify_slack.py -v`
Expected: `12 passed`

**Step 5: Commit**

```bash
git add spotify_slack.py tests/test_spotify_slack.py
git commit -m "feat: add build_slack_profile and build_clear_profile helpers"
```

---

## Task 4: Logging setup

**Files:**
- Modify: `C:\Users\charl\Documents\SpotifySlack\spotify_slack.py`

**Step 1: Add logging configuration**

Add at the top of `spotify_slack.py`, after imports:

```python
import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_PATH = Path(__file__).parent / "spotify_slack.log"


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
```

**Step 2: Sanity check — import the module**

Run: `.venv/Scripts/python -c "import spotify_slack; spotify_slack.configure_logging(); print('ok')"`
Expected: `ok` (and a `spotify_slack.log` file created next to the script).

**Step 3: Clean up the stray log file before committing**

Run: `rm spotify_slack.log*`

**Step 4: Run the test suite to confirm nothing broke**

Run: `.venv/Scripts/python -m pytest tests/test_spotify_slack.py -v`
Expected: `12 passed`

**Step 5: Commit**

```bash
git add spotify_slack.py
git commit -m "feat: add rotating file logging with DEBUG env flag"
```

---

## Task 5: Config loading

**Files:**
- Modify: `C:\Users\charl\Documents\SpotifySlack\spotify_slack.py`
- Modify: `C:\Users\charl\Documents\SpotifySlack\tests\test_spotify_slack.py`

**Step 1: Write the failing tests**

Append to `tests/test_spotify_slack.py`:

```python
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
```

**Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_spotify_slack.py -v`
Expected: `ImportError: cannot import name 'Config'`

**Step 3: Add `Config` and `load_config`**

Add to `spotify_slack.py`:

```python
from dataclasses import dataclass


class ConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class Config:
    spotify_client_id: str
    spotify_client_secret: str
    spotify_redirect_uri: str
    slack_user_token: str


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
```

**Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_spotify_slack.py -v`
Expected: `14 passed`

**Step 5: Commit**

```bash
git add spotify_slack.py tests/test_spotify_slack.py
git commit -m "feat: add Config dataclass and load_config with .env support"
```

---

## Task 6: Spotify + Slack client factories

**Files:**
- Modify: `C:\Users\charl\Documents\SpotifySlack\spotify_slack.py`

**Step 1: Add factories**

Add to `spotify_slack.py`:

```python
SPOTIFY_SCOPE = "user-read-currently-playing"
SPOTIFY_CACHE_PATH = Path(__file__).parent / ".spotify_cache"


def make_spotify_client(cfg):
    from spotipy import Spotify
    from spotipy.oauth2 import SpotifyOAuth

    auth = SpotifyOAuth(
        client_id=cfg.spotify_client_id,
        client_secret=cfg.spotify_client_secret,
        redirect_uri=cfg.spotify_redirect_uri,
        scope=SPOTIFY_SCOPE,
        cache_path=str(SPOTIFY_CACHE_PATH),
        open_browser=False,
    )
    return Spotify(auth_manager=auth)


def make_slack_client(cfg):
    from slack_sdk import WebClient
    return WebClient(token=cfg.slack_user_token)
```

**Step 2: Smoke-test the import**

Run: `.venv/Scripts/python -c "import spotify_slack; print(spotify_slack.make_spotify_client, spotify_slack.make_slack_client)"`
Expected: prints two function objects, no errors.

**Step 3: Run tests to confirm nothing broke**

Run: `.venv/Scripts/python -m pytest -v`
Expected: `14 passed`

**Step 4: Commit**

```bash
git add spotify_slack.py
git commit -m "feat: add Spotify and Slack client factories"
```

---

## Task 7: Main poll-iteration function with mocked tests

**Files:**
- Modify: `C:\Users\charl\Documents\SpotifySlack\spotify_slack.py`
- Modify: `C:\Users\charl\Documents\SpotifySlack\tests\test_spotify_slack.py`

**Step 1: Write the failing tests**

Append to `tests/test_spotify_slack.py`:

```python
from unittest.mock import MagicMock
from spotify_slack import State, poll_once


def _playing(track_id, name="Song", artists=("Artist",)):
    return {
        "is_playing": True,
        "item": {
            "id": track_id,
            "name": name,
            "artists": [{"name": a} for a in artists],
        },
    }


def test_poll_once_new_track_updates_slack():
    spotify = MagicMock()
    slack = MagicMock()
    spotify.current_user_playing_track.return_value = _playing("abc")
    state = State()

    new_state = poll_once(spotify, slack, state)

    slack.users_profile_set.assert_called_once()
    profile = slack.users_profile_set.call_args.kwargs["profile"]
    assert profile["status_text"] == "Song — Artist"
    assert profile["status_emoji"] == ":musical_note:"
    assert new_state.last_track_id == "abc"
    assert new_state.last_cleared is False


def test_poll_once_same_track_no_call():
    spotify = MagicMock()
    slack = MagicMock()
    spotify.current_user_playing_track.return_value = _playing("abc")
    state = State(last_track_id="abc", last_cleared=False)

    new_state = poll_once(spotify, slack, state)

    slack.users_profile_set.assert_not_called()
    assert new_state == state


def test_poll_once_stopped_clears_once():
    spotify = MagicMock()
    slack = MagicMock()
    spotify.current_user_playing_track.return_value = None
    state = State(last_track_id="abc", last_cleared=False)

    new_state = poll_once(spotify, slack, state)

    slack.users_profile_set.assert_called_once_with(
        profile={"status_text": "", "status_emoji": ""}
    )
    assert new_state.last_cleared is True
    assert new_state.last_track_id is None


def test_poll_once_stopped_already_cleared_no_call():
    spotify = MagicMock()
    slack = MagicMock()
    spotify.current_user_playing_track.return_value = None
    state = State(last_track_id=None, last_cleared=True)

    new_state = poll_once(spotify, slack, state)

    slack.users_profile_set.assert_not_called()
    assert new_state.last_cleared is True
```

**Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_spotify_slack.py -v`
Expected: `ImportError: cannot import name 'State'`

**Step 3: Add `State` and `poll_once`**

Add to `spotify_slack.py`:

```python
@dataclass(frozen=True)
class State:
    last_track_id: str | None = None
    last_cleared: bool = False


log = logging.getLogger("spotify_slack")


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
```

**Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_spotify_slack.py -v`
Expected: `18 passed`

**Step 5: Commit**

```bash
git add spotify_slack.py tests/test_spotify_slack.py
git commit -m "feat: add poll_once with State and tests"
```

---

## Task 8: `setup.py` — one-time Spotify OAuth bootstrap

**Files:**
- Create: `C:\Users\charl\Documents\SpotifySlack\setup.py`

**Step 1: Write `setup.py`**

```python
"""One-time Spotify OAuth bootstrap.

Run this once after filling in .env. Opens a browser (or prints a URL) so
you can authorize the app. A refresh token is then cached at .spotify_cache
and used by spotify_slack.py on startup.
"""
from spotify_slack import load_config, make_spotify_client


def main():
    cfg = load_config()
    spotify = make_spotify_client(cfg)
    # Calling any authenticated endpoint forces the OAuth flow if no cache exists.
    me = spotify.current_user()
    print(f"Authorized as: {me['display_name']} ({me['id']})")
    print("Cache written to .spotify_cache — you can now run spotify_slack.py")


if __name__ == "__main__":
    main()
```

**Step 2: Add `user-read-private` scope temporarily... or not**

Actually `current_user` works with `user-read-currently-playing`? It does NOT — `current_user` needs `user-read-private`. Use the target endpoint instead so the scope stays minimal. Replace `spotify.current_user()` with:

```python
    playing = spotify.current_user_playing_track()
    print("Authorized. Currently playing:", playing["item"]["name"] if playing and playing.get("item") else "nothing")
```

**Step 3: Sanity-check the import**

Run: `.venv/Scripts/python -c "import setup; print('ok')"`
Expected: `ok`

**Note:** we do NOT actually execute `python setup.py` here — that would try to open a browser and require real credentials. The user runs it manually during setup.

**Step 4: Run the test suite**

Run: `.venv/Scripts/python -m pytest -v`
Expected: `18 passed`

**Step 5: Commit**

```bash
git add setup.py
git commit -m "feat: add setup.py for one-time Spotify OAuth bootstrap"
```

---

## Task 9: Main loop with error handling

**Files:**
- Modify: `C:\Users\charl\Documents\SpotifySlack\spotify_slack.py`

**Step 1: Add the main loop**

Add to `spotify_slack.py`:

```python
import time

POLL_INTERVAL_SECONDS = 60


def run_forever():
    configure_logging()
    log.info("starting spotify_slack")
    cfg = load_config()
    spotify = make_spotify_client(cfg)
    slack = make_slack_client(cfg)
    state = State()

    while True:
        try:
            state = poll_once(spotify, slack, state)
        except KeyboardInterrupt:
            log.info("shutting down on KeyboardInterrupt")
            return
        except Exception:
            log.exception("error in poll iteration; continuing")
        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    run_forever()
```

**Step 2: Verify the file still imports**

Run: `.venv/Scripts/python -c "import spotify_slack; print('ok')"`
Expected: `ok`

**Step 3: Run the full test suite**

Run: `.venv/Scripts/python -m pytest -v`
Expected: `18 passed`

**Step 4: Commit**

```bash
git add spotify_slack.py
git commit -m "feat: add run_forever main loop with top-level error handling"
```

---

## Task 10: `run.bat` launcher

**Files:**
- Create: `C:\Users\charl\Documents\SpotifySlack\run.bat`

**Step 1: Write `run.bat`**

```bat
@echo off
cd /d "%~dp0"
call .venv\Scripts\activate.bat
start "" /b pythonw spotify_slack.py
```

**Step 2: Commit**

```bash
git add run.bat
git commit -m "feat: add run.bat launcher for Windows Startup folder"
```

---

## Task 11: Final verification

**Step 1: Run the full test suite one last time**

Run: `.venv/Scripts/python -m pytest -v`
Expected: `18 passed`

**Step 2: Confirm the layout matches the design**

Run: `ls C:/Users/charl/Documents/SpotifySlack`
Expected output includes: `spotify_slack.py`, `setup.py`, `run.bat`, `requirements.txt`, `.env.example`, `.gitignore`, `README.md`, `docs/`, `tests/`.

**Step 3: Confirm secrets are gitignored**

Create a dummy `.env` and `.spotify_cache`:

```
echo "SPOTIFY_CLIENT_ID=fake" > .env
echo "fake" > .spotify_cache
git status --short
```

Expected: neither `.env` nor `.spotify_cache` appears in `git status`. Then delete the dummy files:

```
rm .env .spotify_cache
```

**Step 4: Print the setup reminder for the user**

The user still needs to:
1. Fill in `.env` with real credentials (README walks through this)
2. Run `python setup.py` once to authorize Spotify
3. Drop a shortcut to `run.bat` into `shell:startup`

Plan complete.

---

## Notes for the executor

- Every code block in this plan is the complete, final version for that task. Do not add features, logging, or error handling beyond what's shown.
- Run tests after every code change, even "trivial" ones.
- Commit after every task. Do not squash.
- If a test fails unexpectedly, STOP and debug before moving on. Do not skip tests.
- `spotify_slack.py` is built incrementally; by Task 9 it contains everything from Tasks 1–7 plus the main loop. Do not rewrite previous sections.
