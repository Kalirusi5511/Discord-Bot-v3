import datetime
import os
from threading import Thread
import discord
from discord import app_commands
from flask import Flask
import requests

# 1. Webserver für Render.com 🌐
app = Flask(__name__)


@app.route("/")
def home():
  return "Bot läuft online! 🟢"


def run_webserver():
  # Render weist automatisch einen freien Port zu (Standard 10000)
  port = int(os.environ.get("PORT", 10000))
  app.run(host="0.0.0.0", port=port)


# 2. Token & Webhook aus den Umgebungsvariablen laden 🔑
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

# 3. Intents (Berechtigungen) & Client-Setup 🤖
intents = discord.Intents.default()
intents.presences = True  # Online-Status überwachen 🟢
intents.members = True  # Server-Mitglieder abfragen 👥

client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)


# 4. Hilfsfunktion für Webhook-Logs 📤
def send_webhook_log(message):
  if WEBHOOK_URL:
    data = {"content": message}
    try:
      requests.post(WEBHOOK_URL, json=data)
    except Exception as e:
      print(f"Fehler beim Senden an den Webhook: {e}")
  else:
    print("⚠️ Kein WEBHOOK_URL angegeben!")


# 5. Slash Command (/status) definieren 📜
@tree.command(
    name="status",
    description="Zeigt den aktuellen Online-Status eines Mitglieds an",
)
async def status_command(
    interaction: discord.Interaction, member: discord.Member
):
  status_emojis = {
      discord.Status.online: "🟢 Online",
      discord.Status.idle: "🟡 Abwesend (Idle)",
      discord.Status.dnd: "🔴 Bitte nicht stören (DND)",
      discord.Status.offline: "⚫ Offline",
  }
  aktueller_status = status_emojis.get(
      member.status, f"❓ Unbekannt ({member.status})"
  )

  # Antwort an den Nutzer im Discord-Chat 💬
  await interaction.response.send_message(
      f"Der Status von **{member.name}** ist: {aktueller_status}"
  )


# 6. Bot-Ereignisse (Events) ⚡
@client.event
async def on_ready():
  # Synchronisiert die Befehle mit Discord 🚀
  await tree.sync()
  print(
      f"🟢 Log-Bot läuft auf Render als {client.user} und Slash Commands sind"
      " aktiv!"
  )


@client.event
async def on_presence_update(before: discord.Member, after: discord.Member):
  if before.status != after.status:
    zeitstempel = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Status-Änderungen prüfen 🔍
    if after.status == discord.Status.offline:
      log_text = f"[{zeitstempel}] 🔴 **{after.name}** hat Discord geschlossen (Offline)"
    elif before.status == discord.Status.offline:
      log_text = f"[{zeitstempel}] 🟢 **{after.name}** ist wieder online (`{after.status}`)"
    else:
      log_text = f"[{zeitstempel}] 🟡 **{after.name}**: Status geändert von `{before.status}` zu `{after.status}`"

    print(log_text)
    send_webhook_log(log_text)


# 7. Bot & Webserver starten 🚀
if __name__ == "__main__":
  # Flask im Hintergrund starten, damit Render den offenen Port findet
  server_thread = Thread(target=run_webserver)
  server_thread.daemon = True
  server_thread.start()

  if DISCORD_TOKEN:
    client.run(DISCORD_TOKEN)
  else:
    print("❌ FEHLER: Kein DISCORD_TOKEN in den Umgebungsvariablen gefunden!")
