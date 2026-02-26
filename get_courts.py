"""
Pittsburgh RecDesk Pickleball Court Availability Scraper
Usage: python get_courts.py
       python get_courts.py --date 2026-03-01
       python get_courts.py --date 2026-03-01 --time 10:00
       python get_courts.py --location frick schenley --date 2026-03-01 --time 14:00
"""

import requests
import argparse
from datetime import date, datetime
from urllib.parse import urlparse, parse_qs
from bs4 import BeautifulSoup

BASE_URL = "https://pittsburgh.recdesk.com/Community"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": f"{BASE_URL}/Facility?type=20",
}

LOCATIONS = {
    "allegheny": "Allegheny",
    "bud-hammer": "Bud Hammer",
    "fineview": "Fineview",
    "frick": "Frick",
    "schenley": "Schenley",
    "washingtons-landing": "Washington",
}


def get_session():
    session = requests.Session()
    session.headers.update(HEADERS)
    session.get(f"{BASE_URL}/Facility?type=20")
    return session


def get_all_facilities(session):
    payload = {
        "FacilityName": "",
        "FacilityNameXS": "",
        "FacilityType": "20",
        "Pagination": {"CurrentPageIndex": 1, "LoadMore": True},
    }
    resp = session.post(
        f"{BASE_URL}/Facility/FilterFacilities",
        json=payload,
        headers={"Content-Type": "application/json"},
    )
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    facilities = []
    for a in soup.select("a.text-semibold.text-primary[href*='facilityId']"):
        qs = parse_qs(urlparse(a["href"]).query)
        fid = qs.get("facilityId", [None])[0]
        name = a.get_text(strip=True)
        addr_tag = a.find_next("small", class_="text-muted")
        addr = addr_tag.get_text(strip=True) if addr_tag else ""
        facilities.append({"Id": fid, "Name": name, "Address": addr})
    return sorted(facilities, key=lambda x: x["Id"])


def get_availability(session, facility_id, check_date: date):
    """Return list of available time slot dicts for a facility on a given date."""
    date_str = check_date.strftime("%Y-%m-%d")
    resp = session.post(
        f"{BASE_URL}/Facility/GetAvailabilityItems",
        data={
            "facilityId": facility_id,
            "startDate": date_str,
            "endDate": date_str,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    if resp.status_code == 200 and resp.text.strip():
        try:
            return resp.json()
        except Exception:
            pass
    return None


def to_24h(time_str):
    """Convert '7:00 AM' or '07:00' to '07:00'."""
    time_str = time_str.strip()
    for fmt in ("%I:%M %p", "%H:%M"):
        try:
            return datetime.strptime(time_str, fmt).strftime("%H:%M")
        except ValueError:
            continue
    return time_str


def first_available_after(slots, after_time=None):
    """
    Return (start_display, duration_minutes) for the first slot at or after
    after_time (HH:MM), following consecutive slots to compute total duration.
    If after_time is None, use the very first slot.
    Returns None if no qualifying slot exists.
    """
    if not slots:
        return None

    # Parse all slots into (start_dt, end_dt, display_start) sorted by start
    parsed = []
    for s in slots:
        iso = s.get("StartTimeISO8601", "")
        end_iso = s.get("EndTimeISO8601", "")
        display = s.get("StartTimeTimeOnly", "")
        try:
            start_dt = datetime.fromisoformat(iso.replace("Z", "+00:00")).replace(
                tzinfo=None
            )
            end_dt = datetime.fromisoformat(end_iso.replace("Z", "+00:00")).replace(
                tzinfo=None
            )
            parsed.append((start_dt, end_dt, display))
        except Exception:
            continue
    parsed.sort(key=lambda x: x[0])

    # Find the first slot at or after the requested time
    if after_time:
        after_24 = to_24h(after_time)
        cutoff = datetime.strptime(after_24, "%H:%M").replace(
            year=parsed[0][0].year, month=parsed[0][0].month, day=parsed[0][0].day
        )
        candidates = [(s, e, d) for s, e, d in parsed if s >= cutoff]
    else:
        candidates = parsed

    if not candidates:
        return None

    # Walk consecutive slots to compute total continuous duration
    first_start, cur_end, first_display = candidates[0]
    for start_dt, end_dt, _ in candidates[1:]:
        if start_dt == cur_end:
            cur_end = end_dt
        else:
            break

    total_minutes = int((cur_end - first_start).total_seconds() // 60)
    return first_display, total_minutes


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

    check_date = datetime.strptime(args.date, "%Y-%m-%d").date()

    session = get_session()
    facilities = get_all_facilities(session)

    if args.location:
        keywords = [LOCATIONS[loc].lower() for loc in args.location]
        facilities = [
            f for f in facilities if any(kw in f["Name"].lower() for kw in keywords)
        ]

    if not facilities:
        print("No facilities found.")
        return

    if args.list_only:
        return

    time_label = f" from {args.time}" if args.time else ""
    print(f"\nChecking courts in {', '.join (args.location)}...")
    print(f"\n=== Available courts on {check_date}{time_label} ===\n")

    available = []
    for f in facilities:
        slots = get_availability(session, f["Id"], check_date)
        if not slots:
            continue
        result = first_available_after(slots, after_time=args.time)
        if result:
            available.append((f["Name"], result[0], result[1]))

    if not available:
        print("  No courts available.")
        return

    name_w = max(len(name) for name, _, _ in available) + 2
    for name, start, duration in available:
        hrs, mins = divmod(duration, 60)
        dur_str = f"{hrs}h {mins}m" if hrs else f"{mins}m"
        print(f"  {name:<{name_w}}  available from {start}  ({dur_str})")


if __name__ == "__main__":
    main()
