import datetime
import os
import discord

# 1. Token sicher aus den Umgebungsvariablen von Render laden
TOKEN = os.getenv("DISCORD_TOKEN")

# 2. Intents (Berechtigungen) festlegen
intents = discord.Intents.default()
intents.presences = True  # Statusänderungen überwachen 🟢
intents.members = True  # Server-Mitglieder lesen

client = discord.Client(intents=intents)


@client.event
async def on_ready():
  print(f"🟢 Log-Bot läuft erfolgreich auf Render.com als {client.user}")


@client.event
async def on_presence_update(before: discord.Member, after: discord.Member):
  if before.status != after.status:
    zeitstempel = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if after.status == discord.Status.offline:
      log_text = f"[{zeitstempel}] 🔴 {after.name} hat Discord geschlossen (Offline)\n"
    elif before.status == discord.Status.offline:
      log_text = f"[{zeitstempel}] 🟢 {after.name} ist wieder online ({after.status})\n"
    else:
      log_text = (
          f"[{zeitstempel}] 🟡 {after.name}: {before.status} ➔ {after.status}\n"
      )

    # Auf Render sehen wir die Logs direkt in der Render-Konsole!
    print(log_text.strip())

    # Optional: Lokal/im Container in eine Datei schreiben
    with open("user_presence.log", "a", encoding="utf-8") as log_file:
      log_file.write(log_text)


if __name__ == "__main__":
  if not TOKEN:
    print("❌ FEHLER: Kein DISCORD_TOKEN gefunden!")
  else:
    client.run(TOKEN)
