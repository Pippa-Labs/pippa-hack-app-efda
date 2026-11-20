"""Preview CampusFit's answers without the Pippa SDK.

    python3 scripts/preview.py                      # Judo + Climbing, then events
    python3 scripts/preview.py --clubs "Judo"       # just Judo
    python3 scripts/preview.py --host union         # only Union events
    python3 scripts/preview.py --now 2026-11-20T09:00

It uses the same sample data and clash logic as the app (`campusfit.py`). It
does not run `app.py`, which needs the SDK that only the build installs, so
the exact `data` shape is checked by the tests in the build, not here.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import campusfit  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--clubs", default="", help='e.g. "Judo, Climbing"')
    parser.add_argument("--host", default="", help="imperial, union, or empty for both")
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--now", default="", help="London time, e.g. 2026-11-20T09:00")
    args = parser.parse_args()

    now = (datetime.fromisoformat(args.now).replace(tzinfo=campusfit.LONDON)
           if args.now else datetime.now(campusfit.LONDON))
    clubs = campusfit.parse_clubs(args.clubs) or list(campusfit.DEFAULT_FOLLOWED)

    print(f"Now: {now:%a %d %b %Y %H:%M} (London), looking {args.days} days ahead\n")
    print(f"Followed clubs: {', '.join(clubs)}")
    sessions = campusfit.club_sessions(clubs, now, args.days)
    for s in sessions:
        print(f"  {'OK   ' if not s.clash else 'CLASH'}  {s.describe()}")
    nxt = next((s for s in sessions if not s.clash), None)
    print(f"  Next you can attend: {nxt.describe() if nxt else 'none'}\n")

    host = campusfit.parse_host(args.host)
    print(f"Discover ({host or 'Imperial and Union'} events)")
    for e in campusfit.campus_events(host, now, args.days):
        print(f"  {'OK   ' if not e.clash else 'CLASH'}  {e.describe()}")


if __name__ == "__main__":
    main()
