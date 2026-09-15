import datetime
import os
from threading import Thread
import discord
from flask import Flask
import requests

# 1. Webserver für Render.com 🌐
app = Flask(__name__)


@app.route("/")
def home():
  return "Bot läuft online! 🟢"


def run_webserver():
  # Render weist automatisch den benötigten Port zu (Standard ist 10000)
  port = int(os.environ.get("PORT", 10000))
  app.run(host="0.0.0.0", port=port)


# 2. Token & Webhook aus den Umgebungsvariablen laden 🔑
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

# 3. Intents (Berechtigungen) festlegen
intents = discord.Intents.default()
intents.presences = True  # Erlaubt das Überwachen des Online-Status 🟢
intents.members = True  # Erlaubt Zugriff auf Server-Mitglieder

client = discord.Client(intents=intents)


# Funktion zum Senden von Nachrichten über den Webhook 📤
def send_webhook_log(message):
  if WEBHOOK_URL:
    data = {"content": message}
    try:
      requests.post(WEBHOOK_URL, json=data)
    except Exception as e:
      print(f"Fehler beim Senden an den Webhook: {e}")
  else:
    print("⚠️ Kein WEBHOOK_URL angegeben!")


# 4. Bot-Ereignisse ⚡
@client.event
async def on_ready():
  print(f"🟢 Log-Bot läuft erfolgreich auf Render als {client.user}")


@client.event
async def on_presence_update(before: discord.Member, after: discord.Member):
  # Nur reagieren, wenn sich der Status geändert hat
  if before.status != after.status:
    zeitstempel = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Status-Änderungen auswerten
    if after.status == discord.Status.offline:
      log_text = f"[{zeitstempel}] 🔴 **{after.name}** hat Discord geschlossen (Offline)"
    elif before.status == discord.Status.offline:
      log_text = f"[{zeitstempel}] 🟢 **{after.name}** ist wieder online (`{after.status}`)"
    else:
      log_text = f"[{zeitstempel}] 🟡 **{after.name}**: Status geändert von `{before.status}` zu `{after.status}`"

    # Ausgabe in die Render-Konsole
    print(log_text)

    # Direkt über den Webhook in deinen Discord-Kanal senden 🚀
    send_webhook_log(log_text)


# 5. Hauptprogramm starten 🚀
if __name__ == "__main__":
  # Webserver im Hintergrund starten, damit Render den Port sofort findet
  server_thread = Thread(target=run_webserver)
  server_thread.daemon = True
  server_thread.start()

  # Discord Bot starten
  if DISCORD_TOKEN:
    client.run(DISCORD_TOKEN)
  else:
    print("❌ FEHLER: Kein DISCORD_TOKEN in den Umgebungsvariablen gefunden!")
