python
import datetime
import os
from threading import Thread

import discord
from discord import app_commands
from flask import Flask
import requests


# =========================================================
# 1. Render Webserver
# =========================================================

app = Flask(__name__)


@app.route("/")
def home():
    return "Bot läuft online! 🟢"


def run_webserver():
    port = int(os.environ.get("PORT", 10000))

    app.run(
        host="0.0.0.0",
        port=port
    )


# =========================================================
# 2. Environment Variables
# =========================================================

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")


# =========================================================
# 3. Discord Client
# =========================================================

intents = discord.Intents.default()

intents.presences = True
intents.members = True

client = discord.Client(
    intents=intents
)

tree = app_commands.CommandTree(client)


# =========================================================
# 4. Status-Namen
# =========================================================

STATUS_NAMES = {
    discord.Status.online: ("🟢", "Online"),
    discord.Status.idle: ("🟡", "Idle"),
    discord.Status.dnd: ("🔴", "DND"),
    discord.Status.offline: ("⚫", "Offline"),
}


def status_info(status):

    return STATUS_NAMES.get(
        status,
        ("❓", str(status))
    )


# =========================================================
# 5. Zeit
# =========================================================

def get_timestamp():

    # UTC verwenden und Discord-kompatiblen Timestamp erzeugen
    now = datetime.datetime.now(
        datetime.timezone.utc
    )

    return now.strftime(
        "%d.%m.%Y %H:%M:%S UTC"
    )


# =========================================================
# 6. Aktivitäten auslesen
# =========================================================

def get_activities(member):

    activities = []

    for activity in member.activities:

        # Custom Status
        if isinstance(
            activity,
            discord.CustomActivity
        ):

            if activity.name:

                activities.append(
                    f"💬 Custom Status: {activity.name}"
                )

            continue

        # Spotify
        if isinstance(
            activity,
            discord.Spotify
        ):

            activities.append(
                f"🎵 Spotify: "
                f"{activity.title} – {activity.artist}"
            )

            continue

        # Normale Aktivität / Spiel
        if activity.name:

            activity_type = str(
                activity.type
            ).replace(
                "ActivityType.",
                ""
            )

            activities.append(
                f"🎮 {activity_type}: "
                f"{activity.name}"
            )

    if not activities:

        return ["Keine Aktivität"]

    return activities


# =========================================================
# 7. Geräte ermitteln
# =========================================================

def get_devices(member):

    devices = []

    # Discord Presence stellt diese Informationen
    # abhängig von der Presence zur Verfügung.

    if member.desktop_status != discord.Status.offline:
        devices.append("🖥️ PC")

    if member.mobile_status != discord.Status.offline:
        devices.append("📱 Mobile")

    if member.web_status != discord.Status.offline:
        devices.append("🌐 Web")

    if not devices:
        return ["Nicht verfügbar"]

    return devices


# =========================================================
# 8. Webhook senden
# =========================================================

def send_webhook_embed(
    member,
    before,
    after
):

    if not WEBHOOK_URL:

        print(
            "⚠️ Keine WEBHOOK_URL angegeben!"
        )

        return

    before_icon, before_name = status_info(
        before.status
    )

    after_icon, after_name = status_info(
        after.status
    )

    activities = get_activities(after)
    devices = get_devices(after)

    activity_text = "\n".join(
        activities
    )

    device_text = "\n".join(
        devices
    )

    embed = {
        "title": "📡 Presence-Änderung",

        "description": (
            f"**{after.display_name}** "
            f"hat seine Discord-Presence geändert."
        ),

        "color": 0x5865F2,

        "fields": [

            {
                "name": "👤 Benutzer",
                "value": (
                    f"**{after.display_name}**\n"
                    f"`{after.id}`"
                ),
                "inline": True
            },

            {
                "name": "🔄 Status",
                "value": (
                    f"{before_icon} {before_name}"
                    f" → "
                    f"{after_icon} {after_name}"
                ),
                "inline": True
            },

            {
                "name": "💻 Gerät",
                "value": device_text,
                "inline": True
            },

            {
                "name": "🎮 Aktivität",
                "value": activity_text[:1024],
                "inline": False
            },

            {
                "name": "🕐 Zeitpunkt",
                "value": get_timestamp(),
                "inline": False
            }
        ],

        "footer": {
            "text": "Discord Presence Logger"
        }
    }

    payload = {
        "embeds": [embed]
    }

    try:

        response = requests.post(
            WEBHOOK_URL,
            json=payload,
            timeout=10
        )

        if response.status_code >= 400:

            print(
                "⚠️ Webhook-Fehler:",
                response.status_code,
                response.text
            )

    except requests.RequestException as error:

        print(
            f"⚠️ Webhook-Verbindung fehlgeschlagen: {error}"
        )


# =========================================================
# 9. /status
# =========================================================

@tree.command(
    name="status",
    description="Zeigt die Presence eines Mitglieds"
)
async def status_command(
    interaction: discord.Interaction,
    member: discord.Member
):

    icon, status = status_info(
        member.status
    )

    activities = get_activities(
        member
    )

    devices = get_devices(
        member
    )

    embed = discord.Embed(
        title=f"📡 Status von {member.display_name}",
        color=discord.Color.blurple()
    )

    embed.add_field(
        name="Status",
        value=f"{icon} {status}",
        inline=True
    )

    embed.add_field(
        name="Gerät",
        value="\n".join(devices),
        inline=True
    )

    embed.add_field(
        name="Aktivität",
        value="\n".join(activities)[:1024],
        inline=False
    )

    embed.set_footer(
        text=f"User ID: {member.id}"
    )

    await interaction.response.send_message(
        embed=embed
    )


# =========================================================
# 10. Bot Ready
# =========================================================

@client.event
async def on_ready():

    try:

        synced = await tree.sync()

        print(
            f"🟢 Bot online als {client.user}"
        )

        print(
            f"📜 {len(synced)} Slash Command(s) synchronisiert"
        )

        print(
            "👀 Presence-Logger aktiv"
        )

    except Exception as error:

        print(
            f"❌ Fehler bei tree.sync(): {error}"
        )


# =========================================================
# 11. Presence Update
# =========================================================

@client.event
async def on_presence_update(
    before: discord.Member,
    after: discord.Member
):

    # Prüfen, ob sich überhaupt etwas geändert hat
    status_changed = (
        before.status != after.status
    )

    activities_changed = (
        before.activities != after.activities
    )

    desktop_changed = (
        before.desktop_status
        != after.desktop_status
    )

    mobile_changed = (
        before.mobile_status
        != after.mobile_status
    )

    web_changed = (
        before.web_status
        != after.web_status
    )

    # Wenn wirklich gar nichts geändert wurde:
    if not (
        status_changed
        or activities_changed
        or desktop_changed
        or mobile_changed
        or web_changed
    ):
        return

    print(
        f"📡 Presence Update: "
        f"{after.display_name}"
    )

    send_webhook_embed(
        after,
        before,
        after
    )


# =========================================================
# 12. Start
# =========================================================

if __name__ == "__main__":

    server_thread = Thread(
        target=run_webserver,
        daemon=True
    )

    server_thread.start()

    if not DISCORD_TOKEN:

        print(
            "❌ FEHLER: "
            "DISCORD_TOKEN fehlt!"
        )

    else:

        print(
            "🚀 Discord Bot wird gestartet..."
        )

        client.run(
            DISCORD_TOKEN
        )
```
