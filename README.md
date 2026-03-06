# Pball Pete

A Discord bot that checks pickleball court availability at Pittsburgh city parks via the [Pittsburgh RecDesk](https://pittsburgh.recdesk.com/Community/Facility?type=20) reservation system.

---

## What It Does

Users invoke a slash command in Discord to query available courts by date, time, and location. The bot scrapes RecDesk in the background and returns a formatted table of available courts with start times and durations.

---

## Entry Points

| File                      | Purpose                                                    | How to Run                                            |
| ------------------------- | ---------------------------------------------------------- | ----------------------------------------------------- |
| `get_courts.py`           | CLI scraper — no Discord required                          | `python get_courts.py --date 2026-03-09 --time 10:00` |
| `pball_pete.py`           | Flask server — Discord bot backend                         | `python pball_pete.py`                                |
| `create_slash_command.py` | One-time script to register the slash command with Discord | `python create_slash_command.py`                      |

---

## File Overview

```
pball/
├── get_courts_lib.py         # Core scraping library (session, fetch, parse)
├── get_courts.py             # CLI wrapper around the library
├── pball_pete.py             # Flask app, Discord interaction handler
├── create_slash_command.py   # Registers /get_court_availability with Discord
├── Dockerfile                # Container build definition
├── docker-compose.yml        # Container orchestration
├── requirements.txt          # Full dependencies (bot + scraper)
└── script_only_requirements.txt  # Minimal dependencies (scraper/CLI only)
```

---

## Running Locally

### Scraper Only (no Discord setup needed)

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r script_only_requirements.txt

python get_courts.py --date 2026-03-09 --time 10:00 --location washingtons-landing
```

### Full Bot

```bash
pip install -r requirements.txt

export BOT_TOKEN=your_bot_token
export BOT_PUBLIC_KEY=your_bot_public_key
export APPLICATION_ID=your_application_id
export GUILD_ID=your_guild_id

python pball_pete.py
```

Use [ngrok](https://ngrok.com/) to expose `localhost:8181` to Discord during local development:

```bash
ngrok http 8181
```

Then set your **Interactions Endpoint URL** in the [Discord Developer Portal](https://discord.com/developers/applications) to `https://<your-ngrok-url>/interactions`.

### Docker

```bash
# Create a .env file with your credentials
cp .env.example .env  # fill in values

docker compose up --build
```

---

## Discord Slash Command

```
/get_court_availability [date] [time] [location]
```

| Option     | Default              | Format                                   |
| ---------- | -------------------- | ---------------------------------------- |
| `date`     | Next Sunday          | `YYYY-MM-DD`                             |
| `time`     | `10:00`              | `HH:MM` (24-hour)                        |
| `location` | Washington's Landing | See choices in `create_slash_command.py` |

---

## Environment Variables

| Variable         | Required By                                | Description                                       |
| ---------------- | ------------------------------------------ | ------------------------------------------------- |
| `BOT_TOKEN`      | `pball_pete.py`                            | Discord bot token                                 |
| `BOT_PUBLIC_KEY` | `pball_pete.py`                            | Ed25519 public key for verifying Discord requests |
| `APPLICATION_ID` | `pball_pete.py`, `create_slash_command.py` | Discord application ID                            |
| `GUILD_ID`       | `create_slash_command.py`                  | Discord server ID for command registration        |
