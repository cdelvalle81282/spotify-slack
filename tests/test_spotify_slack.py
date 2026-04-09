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
