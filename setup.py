"""One-time Spotify OAuth bootstrap.

Run this once after filling in .env. Opens a browser (or prints a URL) so
you can authorize the app. A refresh token is then cached at .spotify_cache
and used by spotify_slack.py on startup.
"""
from spotify_slack import load_config, make_spotify_client


def main():
    cfg = load_config()
    spotify = make_spotify_client(cfg)
    playing = spotify.current_user_playing_track()
    if playing and playing.get("item"):
        print("Authorized. Currently playing:", playing["item"]["name"])
    else:
        print("Authorized. Nothing currently playing.")
    print("Cache written to .spotify_cache — you can now run spotify_slack.py")


if __name__ == "__main__":
    main()
