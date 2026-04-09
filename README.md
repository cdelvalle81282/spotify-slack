# SpotifySlack

## What this does

A background Python script that polls Spotify every 60 seconds and updates your
Slack status with the currently playing track. It clears the status when
playback stops, and runs automatically at Windows logon.

## Setup walkthrough

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
