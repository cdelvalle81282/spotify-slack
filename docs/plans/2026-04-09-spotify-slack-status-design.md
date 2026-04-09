# Spotify → Slack Status Automation — Design

**Date:** 2026-04-09
**Status:** Approved

## Summary

A background Python script that polls Spotify every 60 seconds and updates the
user's Slack status with the currently playing track. Clears the status when
playback stops. Runs at Windows logon.

## Architecture

Single-file polling loop, run as a background process on Windows via a Startup
folder shortcut. Two external APIs:

- **Spotify Web API** via `spotipy` (handles OAuth refresh automatically)
- **Slack Web API** via `slack_sdk` (`users.profile.set` with a user token)

Config lives in a `.env` file. Spotify refresh token cached to `.spotify_cache`
after a one-time browser-based OAuth flow.

### File layout

```
C:\Users\charl\Documents\SpotifySlack\
├── spotify_slack.py      # main loop
├── setup.py              # one-time Spotify OAuth
├── run.bat               # launcher used by Windows startup shortcut
├── .env                  # credentials (gitignored)
├── .env.example          # template checked into git
├── .spotify_cache        # refresh token cache (gitignored)
├── spotify_slack.log     # rotating log file
├── requirements.txt      # spotipy, slack_sdk, python-dotenv
├── tests/
│   └── test_spotify_slack.py
├── docs/plans/
│   └── 2026-04-09-spotify-slack-status-design.md
└── README.md             # setup walkthrough
```

## Status format

- Text: `{song} — {artist}` (em dash). Multi-artist tracks join artist names
  with `, `.
- Emoji: `:musical_note:`
- Hard cap at 100 characters — truncate with `…` if longer. Slack rejects
  longer status text.

## Data flow & state

### Startup

1. Load `.env` → read `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`,
   `SLACK_USER_TOKEN`.
2. Initialize `spotipy.Spotify` with `SpotifyOAuth` pointed at `.spotify_cache`.
   Scope: `user-read-currently-playing`.
3. Initialize `slack_sdk.WebClient` with the user token.
4. In-memory state: `last_track_id = None`, `last_status_cleared = False`.

### Per-poll logic (every 60s)

```
current = spotify.current_user_playing_track()

if current is None or not current.get("is_playing"):
    if not last_status_cleared:
        slack.users_profile_set(profile={"status_text": "", "status_emoji": ""})
        last_status_cleared = True
        last_track_id = None
    continue

track_id = current["item"]["id"]
if track_id == last_track_id:
    continue  # same song still playing

text, emoji = format_status(current["item"])
slack.users_profile_set(profile={
    "status_text": text,
    "status_emoji": emoji,
    "status_expiration": 0,
})
last_track_id = track_id
last_status_cleared = False
```

The in-memory state prevents redundant Slack API calls — Slack is only hit
when the track changes or playback stops. No persistent state is needed
beyond the Spotify token cache.

## Error handling & resilience

| Error                                  | Handling                                                                 |
|----------------------------------------|--------------------------------------------------------------------------|
| Spotify access token expired           | `spotipy` refreshes automatically via `.spotify_cache` — transparent     |
| Spotify refresh token invalid          | Log error, keep running. Log tells user to re-run `setup.py`.            |
| Spotify 429 rate limit                 | Respect `Retry-After`, sleep, continue                                   |
| Spotify 5xx / network error            | Log warning, skip cycle, retry next poll                                 |
| Slack token invalid                    | Log error and exit — `.env` must be fixed                                |
| Slack 429 rate limit                   | Respect `Retry-After`, resume next cycle                                 |
| Slack 5xx / network error              | Log warning, skip cycle, retry next poll                                 |
| PC sleep/resume                        | `time.sleep(60)` naturally handles this; loop picks up on next iteration |
| Unhandled exception inside loop body   | Top-of-loop `try/except Exception` logs traceback, sleeps, continues     |

**Graceful shutdown:** handle `KeyboardInterrupt` by logging and exiting (do
not clear status — user may want to keep the last one).

**Logging:**
- File: `spotify_slack.log` via `RotatingFileHandler` (1 MB, 3 backups)
- Level: INFO by default, DEBUG when `SPOTIFY_SLACK_DEBUG=1`
- Format: `%(asctime)s %(levelname)s %(message)s`

**Core invariant:** the main loop never crashes. A broad `try/except
Exception` wraps each iteration.

## Testing strategy

Unit tests via `pytest` + `unittest.mock`. No live API integration tests.

**Pure functions to test:**

1. `format_status(track)` — Spotify track dict → `(status_text, status_emoji)`
   - Normal track
   - Multi-artist track
   - Unicode in title
   - Title longer than 100 chars (truncation with `…`)
   - Missing/empty fields (defensive)
2. `build_slack_profile(text, emoji)` — shape of the dict passed to Slack,
   including truncation boundary at exactly 100 chars.
3. `should_update(current_track_id, last_track_id, is_playing, last_cleared)` —
   decision matrix:
   - New track playing → update
   - Same track playing → skip
   - Nothing playing, not yet cleared → clear
   - Nothing playing, already cleared → skip

**Loop smoke test:** runs two iterations of the main loop with mocked
Spotify and Slack clients, asserting the correct calls.

Target: ~10 tests. Goal is locking down pure logic, not simulating APIs.

**Manual verification:** play a song, wait 60 s, check Slack profile. Pause,
wait 60 s, check status cleared.

## Setup walkthrough (README content)

### Prerequisites
- Python 3.10+
- A Spotify account
- A Slack workspace where you can install apps

### Step 1 — Spotify app
1. https://developer.spotify.com/dashboard → log in
2. Create app
3. Name: "My Slack Status"; Redirect URI: `http://127.0.0.1:8888/callback`;
   check "Web API"
4. Save → Settings → copy **Client ID** and **Client Secret**

### Step 2 — Slack app
1. https://api.slack.com/apps → "Create New App" → "From scratch"
2. Name: "Spotify Status"; select workspace
3. Sidebar → "OAuth & Permissions"
4. **User Token Scopes** (not bot) → add `users.profile:write`
5. Top of page → "Install to Workspace" → Allow
6. Copy the **User OAuth Token** (`xoxp-...`)

### Step 3 — Local config
```
cd C:\Users\charl\Documents\SpotifySlack
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
# edit .env: fill in SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SLACK_USER_TOKEN
python setup.py
# browser opens → log into Spotify once → token cached
```

### Step 4 — Run at Windows logon
1. `run.bat` (provided) activates the venv and runs
   `pythonw spotify_slack.py` (no console window).
2. `Win+R` → `shell:startup` → drop a shortcut to `run.bat` there.
3. Log out and back in, or run `run.bat` once manually.

### Step 5 — Verify
Play a song on Spotify. Within 60 s your Slack status should show
`:musical_note: {song} — {artist}`. Pause Spotify; within 60 s it clears.

## Dependencies

```
spotipy>=2.23
slack_sdk>=3.27
python-dotenv>=1.0
```

Dev dependencies: `pytest`.

## Out of scope

- Multiple Slack workspaces
- Custom emoji per genre/album
- Showing podcast episodes (only music tracks)
- Non-Windows support (Linux/macOS would work with a different launcher; the
  Python code is portable)
- A GUI or tray icon
