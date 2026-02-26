from flask import Flask, request, jsonify
from get_courts_lib import get_availability_dict
import requests
import threading
from datetime import datetime, timedelta
import os

from nacl.signing import VerifyKey  # pip install PyNaCl
from nacl.exceptions import BadSignatureError

app = Flask(__name__)

BOT_PUBLIC_KEY = os.environ["BOT_PUBLIC_KEY"]


def validate_date(date_str):
    """Validate date format (YYYY-MM-DD). Returns (is_valid, error_message)."""
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return True, None
    except ValueError:
        return False, f"'{date_str}' invalid. Use YYYY-MM-DD (e.g., 2026-02-26)"


def validate_time(time_str):
    """Validate time format (HH:MM). Returns (is_valid, error_message)."""
    try:
        datetime.strptime(time_str, "%H:%M")
        return True, None
    except ValueError:
        return False, f"'{time_str}' invalid. Use HH:MM in 24-hour format (e.g., 14:00)"


def get_next_sunday():
    """Get the next coming Sunday as YYYY-MM-DD string."""
    today = datetime.now().date()
    days_until_sunday = (6 - today.weekday()) % 7
    if days_until_sunday == 0:
        days_until_sunday = 7
    next_sunday = today + timedelta(days=days_until_sunday)
    return next_sunday.isoformat()


def verify_signature(req):
    """Verify Discord interaction signature."""
    signature = req.headers.get("X-Signature-Ed25519")
    timestamp = req.headers.get("X-Signature-Timestamp")
    body = req.data.decode("utf-8")

    if not signature or not timestamp:
        return False

    try:
        verify_key = VerifyKey(bytes.fromhex(BOT_PUBLIC_KEY))
        verify_key.verify(f"{timestamp}{body}".encode(), bytes.fromhex(signature))
        return True
    except BadSignatureError:
        return False


@app.route("/interactions", methods=["POST"])
def interactions():
    # Verify the request signature
    if not verify_signature(request):
        return jsonify({"error": "Invalid signature"}), 401

    data = request.json

    # Discord sends a PING on setup — must respond with PONG
    if data["type"] == 1:
        return jsonify({"type": 1})

    # Slash command interaction (type 2)
    if data["type"] == 2:
        command = data["data"]["name"]
        if command == "get_court_availability":
            options = {
                opt["name"]: opt["value"] for opt in data["data"].get("options", [])
            }
            check_date = options.get(
                "date", get_next_sunday()
            )  # Default to next Sunday
            after_time = options.get("time", "10:00")  # Default to 10:00
            location = options.get(
                "location", "Washington"
            )  # Default to Washington's Landing
            interaction_token = data.get("token")

            # Validate date and time formats
            date_valid, date_error = validate_date(check_date)
            if not date_valid:
                return jsonify(
                    {
                        "type": 4,
                        "data": {
                            "embeds": [
                                {
                                    "title": "Invalid Date Format",
                                    "description": date_error,
                                    "color": 15158332,  # Red
                                }
                            ]
                        },
                    }
                )

            time_valid, time_error = validate_time(after_time)
            if not time_valid:
                return jsonify(
                    {
                        "type": 4,
                        "data": {
                            "embeds": [
                                {
                                    "title": "Invalid Time Format",
                                    "description": time_error,
                                    "color": 15158332,  # Red
                                }
                            ]
                        },
                    }
                )

            # Immediately return a deferred response so Discord doesn't timeout
            def process_availability():
                try:
                    print(f"[BACKGROUND] Fetching availability...")
                    # If "all" is selected, pass None to get all locations
                    location_names = None if location == "all" else [location]
                    availability = get_availability_dict(
                        check_date, location_names=location_names, after_time=after_time
                    )
                    print(f"[BACKGROUND] Got {len(availability)} courts")

                    if not availability:
                        content = "No courts available for that date and time."
                    else:
                        # Group courts by location
                        grouped = {}
                        for court_name, info in availability.items():
                            # Extract location from court name (e.g., "Frick-Court 1" -> "Frick")
                            location_name = (
                                court_name.split("-")[0].strip()
                                if "-" in court_name
                                else "Other"
                            )
                            if location_name not in grouped:
                                grouped[location_name] = []
                            grouped[location_name].append((court_name, info))

                        # Format as plain text table
                        lines = ["```"]
                        lines.append("AVAILABLE COURTS")
                        lines.append("=" * 60)
                        lines.append(f"Location: {location}")
                        lines.append(f"Date:     {check_date}")
                        lines.append(f"Time:     {after_time} or later")
                        lines.append("=" * 60)

                        for loc in sorted(grouped.keys()):
                            lines.append(f"\n{loc.upper()}")
                            lines.append("-" * 60)
                            for court_name, info in grouped[loc]:
                                # Extract court number/name after location
                                court_label = court_name.replace(f"{loc}-", "").strip()
                                lines.append(
                                    f"  {court_label:<35} {info['start_time']:>6}  {info['duration_str']:>8}"
                                )

                        lines.append("=" * 60)
                        lines.append("```")
                        content = "\n".join(lines)

                    # Send the response via webhook
                    print(f"[BACKGROUND] Sending webhook...")
                    webhook_url = f"https://discord.com/api/webhooks/{data['application_id']}/{interaction_token}"
                    print(f"[BACKGROUND] URL: {webhook_url}")
                    resp = requests.post(
                        webhook_url,
                        json={"content": content},
                    )
                    print(f"[BACKGROUND] Webhook response: {resp.status_code}")
                    if resp.status_code != 204:
                        print(f"[BACKGROUND] Response text: {resp.text}")
                except Exception as e:
                    print(f"[BACKGROUND] ERROR: {e}")
                    import traceback

                    traceback.print_exc()

            # Start background thread to fetch availability
            thread = threading.Thread(target=process_availability)
            thread.daemon = True
            thread.start()

            # Return deferred response immediately (type 5)
            return jsonify(
                {
                    "type": 5,  # DEFERRED_CHANNEL_MESSAGE_WITH_SOURCE
                }
            )

    # Default fallback (no matching command or interaction type)
    return jsonify({"type": 1})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8181)
