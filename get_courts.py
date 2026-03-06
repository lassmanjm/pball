"""
Pittsburgh RecDesk Pickleball Court Availability Scraper CLI
Usage: python get_courts.py
       python get_courts.py --date 2026-03-01
       python get_courts.py --date 2026-03-01 --time 10:00
       python get_courts.py --location frick schenley --date 2026-03-01 --time 14:00
"""

import argparse
from datetime import date, datetime
import get_courts_lib

LOCATIONS = {
    "allegheny": "Allegheny",
    "bud-hammer": "Bud Hammer",
    "fineview": "Fineview",
    "frick": "Frick",
    "schenley": "Schenley",
    "washingtons-landing": "Washington",
}


def main():
    parser = argparse.ArgumentParser(
        description="Pittsburgh pickleball court availability"
    )
    parser.add_argument(
        "--date",
        default=date.today().isoformat(),
        help="Date to check (YYYY-MM-DD), default: today",
    )
    parser.add_argument(
        "--time",
        metavar="HH:MM",
        help="Filter slots to a specific start time, e.g. 10:00",
    )
    parser.add_argument(
        "--location",
        nargs="+",
        choices=LOCATIONS.keys(),
        metavar="LOCATION",
        help=f"Filter by location(s): {', '.join(LOCATIONS.keys())}",
        default=["washingtons-landing"],
    )
    parser.add_argument(
        "--list-only",
        action="store_true",
        help="Just list courts, don't check availability",
    )
    args = parser.parse_args()

    if args.list_only:
        return

    # Map location keys to display names for the library function
    location_names = (
        [LOCATIONS[loc] for loc in args.location] if args.location else None
    )

    time_label = f" from {args.time}" if args.time else ""
    print(f"\nChecking courts in {', '.join (args.location)}...")
    print(f"\n=== Available courts on {args.date}{time_label} ===\n")

    available = get_courts_lib.get_availability_dict(
        args.date, location_names=location_names, after_time=args.time
    )

    if not available:
        print("  No courts available.")
        return

    name_w = max(len(name) for name in available) + 2
    for name, info in available.items():
        print(
            f"  {name:<{name_w}}  available from {info['start_time']}  ({info['duration_str']})\n{info['URL']}"
        )


if __name__ == "__main__":
    main()
