"""Tests for CampusFit, run through LocalRunner so the manifest is enforced.

The build runs these before publishing. They need the Pippa SDK, which only
the build installs.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pippa_agentapp_sdk import LocalRunner, OutputShapeViolation

import campusfit
from app import App, BadDays, UnknownClub

# Friday 20 November 2026, 09:00 in London (GMT, so the same as UTC).
NOW = datetime(2026, 11, 20, 9, 0, tzinfo=timezone.utc)


def call(outcome: str, inputs: dict, *, explicit: bool = False, now=NOW):
    return LocalRunner(App()).call(
        outcome, inputs, granted_secrets={}, now=now, request_id="test-1",
        explicit=explicit,
    ).result


def test_the_manifest_is_valid():
    app = App()
    assert app.manifest.app_id == "hack.app_efda"
    assert [o.id for o in app.manifest.outcomes] == ["clubs.fit", "events.discover"]


# ── The Judo demo: one session clashes, the next one fits ───────────────────


def test_judo_tuesday_clashes_and_thursday_is_next():
    result = call("clubs.fit", {"clubs": "Judo"})
    data = result.data
    assert data["clubs"] == ["Judo"]
    assert len(data["sessions"]) == 2
    assert data["clash_count"] == 1
    assert data["can_attend_count"] == 1

    # Tuesday: the lab at White City ends 18:00, Judo starts 18:15 at South
    # Kensington, and the trip takes about 35 minutes.
    assert "Tue 24 Nov 18:15-20:00" in data["first_clash"]
    assert "Process lab" in data["first_clash"]
    assert "35 min" in data["first_clash"]

    assert "Thu 26 Nov 19:00-21:00" in data["next_attendable"]
    start = data["next_attendable_start"]
    if isinstance(start, str):
        start = datetime.fromisoformat(start)
    assert start == datetime(2026, 11, 26, 19, 0, tzinfo=timezone.utc)
    assert data["sample_data"] is True
    assert "next session you can make is Judo" in result.narrative


def test_travel_buffer_is_what_causes_the_clash():
    """Without travel time the Tuesday session would not overlap anything."""
    tuesday = campusfit.CLUB_SESSIONS["Judo"][0]
    assert tuesday.start > next(t for t in campusfit.TIMETABLE if t.title == "Process lab").end
    assert "getting to South Kensington takes about 35 min" in campusfit.clash_reason(tuesday)


def test_no_clubs_named_uses_the_sample_followed_clubs():
    data = call("clubs.fit", {"clubs": ""}).data
    assert data["clubs"] == ["Judo", "Climbing"]
    assert data["clash_count"] == 2          # Mon climbing overlaps a tutorial, Tue judo
    assert "Climbing, Wed 25 Nov 13:00-15:00" in data["next_attendable"]


def test_several_clubs_written_loosely():
    data = call("clubs.fit", {"clubs": "judo club and Chess society"}).data
    assert data["clubs"] == ["Judo", "Chess"]


def test_an_unknown_club_is_named_in_the_refusal():
    with pytest.raises(UnknownClub) as failure:
        call("clubs.fit", {"clubs": "Quidditch"})
    assert "Quidditch" in failure.value.user_message
    assert "Judo" in failure.value.user_message


def test_days_ahead_widens_the_window():
    data = call("clubs.fit", {"clubs": "Judo", "days_ahead": 14}).data
    assert len(data["sessions"]) == 4


def test_days_ahead_out_of_range_is_refused():
    with pytest.raises(BadDays):
        call("clubs.fit", {"clubs": "Judo", "days_ahead": 365})


def test_a_session_already_started_is_not_upcoming():
    # Thursday 26 November, 19:30: the Thursday session has begun.
    late = datetime(2026, 11, 26, 19, 30, tzinfo=timezone.utc)
    data = call("clubs.fit", {"clubs": "Judo"}, now=late).data
    assert data["sessions"][0].startswith("Judo, Tue 1 Dec")


def test_nothing_that_fits_leaves_the_optional_fields_out():
    # Dance is only on Friday 11:00 at White City, straight after a lecture at
    # Hammersmith that ends at 11:00.
    data = call("clubs.fit", {"clubs": "Dance"}).data
    assert data["can_attend_count"] == 0
    assert "next_attendable" not in data
    assert "next_attendable_start" not in data


# ── Discover ────────────────────────────────────────────────────────────────


def test_discover_lists_imperial_and_union_events():
    result = call("events.discover", {"host": ""})
    data = result.data
    assert data["host"] == "Imperial and Union"
    assert len(data["events"]) == 6
    assert any(e.startswith("Imperial:") for e in data["events"])
    assert any(e.startswith("Union:") for e in data["events"])
    assert data["fits_count"] == 5
    assert data["next_fitting_event"].startswith("Union: Karaoke night, Fri 20 Nov")
    clash = next(e for e in data["events"] if "clashes" in e)
    assert "Innovation showcase" in clash and "Process lab" in clash


@pytest.mark.parametrize("text, host", [
    ("Union", "Union"),
    ("imperial college union", "Union"),
    ("the college", "Imperial"),
    ("Imperial", "Imperial"),
    ("both", "Imperial and Union"),
])
def test_discover_by_host(text, host):
    data = call("events.discover", {"host": text}).data
    assert data["host"] == host
    if host != "Imperial and Union":
        assert all(e.startswith(f"{host}:") for e in data["events"])


def test_discover_with_no_inputs_at_all():
    assert call("events.discover", {}).data["host"] == "Imperial and Union"


# ── Picked with @ ───────────────────────────────────────────────────────────


def test_picked_by_name_it_answers_and_refuses_as_usual():
    assert call("clubs.fit", {"clubs": "Judo"}, explicit=True).data == \
        call("clubs.fit", {"clubs": "Judo"}).data
    with pytest.raises(UnknownClub):
        call("clubs.fit", {"clubs": "Quidditch"}, explicit=True)


def test_the_runner_enforces_the_manifest(monkeypatch):
    from pippa_agentapp_sdk import Result

    monkeypatch.setattr(App, "handle", lambda self, c: Result(data={"surprise": "hello"}))
    with pytest.raises(OutputShapeViolation):
        call("clubs.fit", {"clubs": "Judo"})
