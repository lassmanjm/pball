"""
Pittsburgh RecDesk Pickleball Court Availability Scraper Library
Core functions for fetching and parsing court availability data.
"""

import requests
from datetime import date, datetime
from urllib.parse import urlparse, parse_qs
from bs4 import BeautifulSoup

BASE_URL = "https://pittsburgh.recdesk.com/Community"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": f"{BASE_URL}/Facility?type=20",
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
        href = a["href"]
        qs = parse_qs(urlparse(a["href"]).query)
        fid = qs.get("facilityId", [None])[0]
        name = a.get_text(strip=True)
        addr_tag = a.find_next("small", class_="text-muted")
        addr = addr_tag.get_text(strip=True) if addr_tag else ""
        facilities.append(
            {
                "Id": fid,
                "Name": name,
                "Address": addr,
                "URL": f"{BASE_URL}/Facility/Reserve{href[26:len(href)]}",
            }
        )
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


def check_court_availability(session, facilities, check_date, after_time=None):
    """
    Check availability for a list of facilities and return structured data.

    Returns: {
        "Facility Name": {
            "start_time": "HH:MM",
            "duration_minutes": 90,
            "duration_str": "1h 30m"
        }
    }
    """
    result = {}

    for facility in facilities:
        slots = get_availability(session, facility["Id"], check_date)
        if not slots:
            continue

        availability = first_available_after(slots, after_time=after_time)
        if availability:
            start_time, duration_minutes = availability
            hrs, mins = divmod(duration_minutes, 60)
            duration_str = f"{hrs}h {mins}m" if hrs else f"{mins}m"

            result[facility["Name"]] = {
                "start_time": start_time,
                "duration_minutes": duration_minutes,
                "duration_str": duration_str,
                "URL": facility["URL"],
            }

    return result


def get_availability_dict(check_date, location_names=None, after_time=None):
    """
    Get court availability as a dict for specified locations and date.

    Args:
        check_date: str (YYYY-MM-DD) or date object
        location_names: list of location display names to filter (e.g. ["Schenley", "Washington"])
                       None or empty list returns all locations
        after_time: str (HH:MM) to filter slots starting at or after this time

    Returns: {
        "Facility Name": {
            "start_time": "HH:MM",
            "duration_minutes": 90,
            "duration_str": "1h 30m"
        }
    }
    """
    from datetime import datetime as dt

    # Parse check_date if it's a string
    if isinstance(check_date, str):
        check_date = dt.strptime(check_date, "%Y-%m-%d").date()

    # Get all facilities
    session = get_session()
    all_facilities = get_all_facilities(session)

    # Filter by location if specified
    if location_names:
        location_keywords = [name.lower() for name in location_names]
        facilities = [
            f
            for f in all_facilities
            if any(kw in f["Name"].lower() for kw in location_keywords)
        ]
    else:
        facilities = all_facilities

    if not facilities:
        return {}

    return check_court_availability(
        session, facilities, check_date, after_time=after_time
    )
