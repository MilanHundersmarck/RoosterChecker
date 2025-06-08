import discord
import json
import asyncio
import requests
from ics import Calendar
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
load_dotenv()

TOKEN = os.getenv("TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))
WEBCAL_URL = os.getenv("WEBCAL_URL")
DATA_FILE = "events.json"

intents = discord.Intents.default()
client = discord.Client(intents=intents)

def fetch_events():
    url = WEBCAL_URL.replace("webcal://", "https://")
    response = requests.get(url)
    response.raise_for_status()
    calendar = Calendar(response.text)
    
    today = datetime.today().date()
    events = []
    for e in calendar.events:
        if e.begin.date() >= today:
            events.append({
                "uid": e.uid,
                "start": e.begin.isoformat(),
                "end": e.end.isoformat(),
                "name": e.name
            })
    return sorted(events, key=lambda x: x["start"])

def load_saved_events():
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_events(events):
    with open(DATA_FILE, "w") as f:
        json.dump(events, f, indent=2)

def compare_events(old, new):
    old_dict = {e['uid']: e for e in old}
    new_dict = {e['uid']: e for e in new}

    added = [new_dict[uid] for uid in new_dict if uid not in old_dict]
    removed = [old_dict[uid] for uid in old_dict if uid not in new_dict]
    changed = []
    
    for uid in new_dict:
        if uid in old_dict:
            old_e, new_e = old_dict[uid], new_dict[uid]
            if (old_e['start'] != new_e['start'] or
                old_e['end'] != new_e['end'] or
                old_e['name'] != new_e['name']):
                changed.append((old_e, new_e))

    return added, removed, changed

def format_changes(added, removed, changed):
    lines = ["**Roosterwijziging:** @everyone"]
    
    for e in added:
        date = datetime.fromisoformat(e['start']).strftime('%d-%m')
        time_range = format_time_range(e)
        lines.append(f"- 🟢 **{date}** {time_range}, **{e['name']}** ")
    
    for e in removed:
        date = datetime.fromisoformat(e['start']).strftime('%d-%m')
        time_range = format_time_range(e)
        lines.append(f"- 🔴 **{date}** {time_range}, **{e['name']}**")
    
    for old, new in changed:
        date = datetime.fromisoformat(old['start']).strftime('%d-%m')
        lines.append(f"- ✏️ **{date}**")
        lines.append(f"   • *Vorige:* **{old['name']}** {format_time_range(old)}")
        lines.append(f"   • *Nieuwe:* **{new['name']}** {format_time_range(new)}")
    
    return "\n".join(lines)


def format_time_range(event):
    start = datetime.fromisoformat(event['start']).strftime('%H:%M')
    end = datetime.fromisoformat(event['end']).strftime('%H:%M')
    return f"{start} - {end}"

async def daily_check():
    await client.wait_until_ready()
    channel = client.get_channel(CHANNEL_ID)
    while not client.is_closed():
        try:
            new_events = fetch_events()
            old_events = load_saved_events()

            added, removed, changed = compare_events(old_events, new_events)

            if added or removed or changed:
                message = format_changes(added, removed, changed)
                await channel.send(message)
                save_events(new_events)

        except Exception as e:
            await channel.send(f"Error during calendar check: {e}")

        await asyncio.sleep(1 * 60)  # wait 24h

@client.event
async def on_ready():
    print(f"Logged in as {client.user}")
    client.loop.create_task(daily_check())

client.run(TOKEN)
