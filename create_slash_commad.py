import requests
import os

APP_ID = os.environ["APPLICATION_ID"]
BOT_TOKEN = os.environ["BOT_TOKEN"]
GUILD_ID = os.environ["GUILD_ID"]

commands = {
    "name": "get_court_availability",
    "description": "Get pickleball court availabilty",
    "type": 1,
    "options": [
        {
            "name": "date",
            "description": "The date (YYYY-MM-DD) - DEFAULT: Sunday",
            "type": 3,  # STRING — Discord has no native date type
            "required": False,
        },
        {
            "name": "time",
            "description": "The time (HH:MM) - DEFAULT: 10:00",
            "type": 3,  # STRING — no native time type either
            "required": False,
        },
        {
            "name": "location",
            "description": "Court location - DEFAULT: Washington's Landing",
            "type": 3,  # STRING with choices = enum
            "required": False,
            "choices": [
                {"name": "All Locations", "value": "all"},
                {"name": "Allegheny", "value": "Allegheny"},
                {"name": "Bud Hammer", "value": "Bud Hammer"},
                {"name": "Fineview", "value": "Fineview"},
                {"name": "Frick", "value": "Frick"},
                {"name": "Schenley", "value": "Schenley"},
                {"name": "Washington's Landing", "value": "Washington"},
            ],
        },
    ],
}

r = requests.post(
    f"https://discord.com/api/v10/applications/{APP_ID}/guilds/{GUILD_ID}/commands",
    headers={"Authorization": f"Bot {BOT_TOKEN}"},
    json=commands,
)

print(r.status_code, r.json())
