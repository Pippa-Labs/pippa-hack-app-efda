"""CampusFit: which Imperial club sessions and campus events fit a timetable.

Two outcomes:

* `clubs.fit` — upcoming sessions of the clubs a student follows, which of
  them clash with lectures once travel between campuses is allowed for, and
  the next one they can attend.
* `events.discover` — upcoming Imperial and Union events, and which fit.

The app remembers nothing between calls, so "following" a club means naming
it in the question. When none is named, the sample followed list is used.
The timetable, sessions and events are sample data (see `campusfit.py`), and
nothing is sent anywhere.
"""

from __future__ import annotations

from pathlib import Path

from pippa_agentapp_sdk import (
    AgentAppError,
    Call,
    Manifest,
    Result,
    load_manifest_file,
    validate_manifest,
)

import campusfit

MANIFEST_PATH = Path(__file__).with_name("manifest.yaml")

DEFAULT_DAYS = 7
MAX_DAYS = 28


class UnknownClub(AgentAppError):
    user_message = "I do not know that club."
    retryable = False


class BadDays(AgentAppError):
    user_message = f"I can look between 1 and {MAX_DAYS} days ahead."
    retryable = False


class App:
    def __init__(self) -> None:
        self._manifest = validate_manifest(load_manifest_file(MANIFEST_PATH))

    @property
    def manifest(self) -> Manifest:
        return self._manifest

    def handle(self, call: Call) -> Result:
        days = self._days(call.inputs.get("days_ahead"))
        if call.outcome_id == "clubs.fit":
            return self._clubs(call, days)
        if call.outcome_id == "events.discover":
            return self._events(call, days)
        raise AgentAppError(f"this app cannot do {call.outcome_id!r}")

    # ── clubs.fit ───────────────────────────────────────────────────────────

    def _clubs(self, call: Call, days: int) -> Result:
        try:
            clubs = campusfit.parse_clubs(call.inputs.get("clubs"))
        except campusfit.UnknownClub as exc:
            error = UnknownClub(f"unknown club {exc.name!r}")
            error.user_message = (
                f"I do not know a club called {exc.name}. CampusFit knows: "
                f"{', '.join(campusfit.CLUB_SESSIONS)}."
            )
            raise error from None
        if not clubs:
            clubs = list(campusfit.DEFAULT_FOLLOWED)

        sessions = campusfit.club_sessions(clubs, call.context.now, days)
        fits = [s for s in sessions if not s.clash]
        clashes = [s for s in sessions if s.clash]

        data = {
            "clubs": clubs,
            "sessions": [s.describe() for s in sessions],
            "can_attend_count": len(fits),
            "clash_count": len(clashes),
            "sample_data": True,
        }
        if fits:
            data["next_attendable"] = fits[0].describe()
            data["next_attendable_start"] = fits[0].start
        if clashes:
            data["first_clash"] = clashes[0].describe()

        return Result(data=data, narrative=self._clubs_sentence(clubs, days, fits, clashes))

    @staticmethod
    def _clubs_sentence(clubs, days, fits, clashes) -> str:
        names = " and ".join(clubs)
        if not fits and not clashes:
            return f"There are no {names} sessions in the next {days} days."
        parts = []
        if clashes:
            first = clashes[0]
            parts.append(
                f"{first.slot.title} on {campusfit.when(first.start, first.end)} "
                f"clashes: it {first.clash}."
            )
        if fits:
            nxt = fits[0]
            parts.append(
                f"The next session you can make is {nxt.slot.title} on "
                f"{campusfit.when(nxt.start, nxt.end)} at {nxt.slot.venue}."
            )
        else:
            parts.append(f"None of the {names} sessions in the next {days} days fit.")
        return " ".join(parts) + " (Sample timetable.)"

    # ── events.discover ─────────────────────────────────────────────────────

    def _events(self, call: Call, days: int) -> Result:
        host = campusfit.parse_host(call.inputs.get("host"))
        events = campusfit.campus_events(host, call.context.now, days)
        fits = [e for e in events if not e.clash]
        label = host or "Imperial and Union"

        data = {
            "host": label,
            "events": [e.describe() for e in events],
            "fits_count": len(fits),
            "sample_data": True,
        }
        if fits:
            data["next_fitting_event"] = fits[0].describe()

        if not events:
            narrative = f"There are no {label} events in the next {days} days."
        elif fits:
            first = fits[0]
            narrative = (
                f"{len(fits)} of {len(events)} {label} events in the next {days} "
                f"days fit around your lectures; the next is {first.slot.title} "
                f"on {campusfit.when(first.start, first.end)}. (Sample data.)"
            )
        else:
            narrative = (
                f"None of the {len(events)} {label} events in the next {days} "
                "days fit around your lectures. (Sample data.)"
            )
        return Result(data=data, narrative=narrative)

    # ── shared ──────────────────────────────────────────────────────────────

    @staticmethod
    def _days(value) -> int:
        if value is None:
            return DEFAULT_DAYS
        if not 1 <= value <= MAX_DAYS:
            raise BadDays(f"days_ahead out of range: {value!r}")
        return value
