from flask import Flask, request, jsonify
from get_courts_lib import get_availability_dict
import requests
import threading
from datetime import datetime, timedelta

from nacl.signing import VerifyKey  # pip install PyNaCl
from nacl.exceptions import BadSignatureError

app = Flask(__name__)

PUBLIC_KEY = "c3c19b382aec52f3c52a0a60d6cf1c3350f67d0a3f6d004736e36f24ee62b17b"


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
        verify_key = VerifyKey(bytes.fromhex(PUBLIC_KEY))
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
            check_date = options.get("date", get_next_sunday())  # Default to next Sunday
            after_time = options.get("time", "10:00")  # Default to 10:00
            location = options.get("location", "Washington")  # Default to Washington's Landing
            interaction_token = data.get("token")

            # Immediately return a deferred response so Discord doesn't timeout
            def process_availability():
                try:
                    print(f"[BACKGROUND] Fetching availability...")
                    availability = get_availability_dict(
                        check_date, location_names=[location], after_time=after_time
                    )
                    print(f"[BACKGROUND] Got {len(availability)} courts")

                    if not availability:
                        content = "No courts available for that date and time."
                    else:
                        lines = ["**Available Courts:**\n"]
                        for court_name, info in availability.items():
                            lines.append(
                                f"• {court_name}: {info['start_time']} ({info['duration_str']})"
                            )
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
    app.run(port=8181)
