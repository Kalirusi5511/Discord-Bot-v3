import os
import io
import sqlite3

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
from PIL import Image

# ============================================================
# KONFIGURATION
# ============================================================
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

DB_DIR = "data"
DB_PATH = os.path.join(DB_DIR, "stickers.db")

MAX_FILE_SIZE = 512 * 1024
MAX_DIMENSION = 320
ALLOWED_EXT = {".png", ".apng", ".gif", ".jpg", ".jpeg"}


# ============================================================
# DATENBANK
# ============================================================
def init_db():
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS stickers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            filename TEXT NOT NULL,
            data BLOB NOT NULL,
            uploaded_by INTEGER NOT NULL,
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(guild_id, name)
        )
        """
    )
    conn.commit()
    conn.close()
    print(f"Datenbank bereit: {DB_PATH}")


def db_save(guild_id, name, filename, data, user_id):
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            "INSERT INTO stickers "
            "(guild_id, name, filename, data, uploaded_by) "
            "VALUES (?,?,?,?,?)",
            (guild_id, name, filename, data, user_id),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def db_get(guild_id, name):
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT filename, data, uploaded_by, uploaded_at "
        "FROM stickers WHERE guild_id=? AND name=?",
        (guild_id, name),
    ).fetchone()
    conn.close()
    return row


def db_list(guild_id):
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT name, filename, uploaded_by, uploaded_at "
        "FROM stickers WHERE guild_id=? ORDER BY name",
        (guild_id,),
    ).fetchall()
    conn.close()
    return rows


def db_delete(guild_id, name):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute(
        "DELETE FROM stickers WHERE guild_id=? AND name=?",
        (guild_id, name),
    )
    conn.commit()
    affected = cur.rowcount
    conn.close()
    return affected > 0


def db_rename(guild_id, old_name, new_name):
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.execute(
            "UPDATE stickers SET name=? WHERE guild_id=? AND name=?",
            (new_name, guild_id, old_name),
        )
        conn.commit()
        return cur.rowcount > 0
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


# ============================================================
# HILFSFUNKTIONEN
# ============================================================
def is_owner_or_admin(interaction: discord.Interaction) -> bool:
    if interaction.guild is None:
        return False
    if interaction.guild.owner_id == interaction.user.id:
        return True
    return interaction.user.guild_permissions.administrator


def validate_image(data: bytes, ext: str):
    if len(data) > MAX_FILE_SIZE:
        size_kb = len(data) / 1024
        return False, f"Datei zu gross ({size_kb:.0f} KB). Max 512 KB."

    if ext in {".jpg", ".jpeg", ".png"}:
        try:
            img = Image.open(io.BytesIO(data))
            if img.width > MAX_DIMENSION or img.height > MAX_DIMENSION:
                return (
                    False,
                    f"Bild zu gross ({img.width}x{img.height}). "
                    f"Max {MAX_DIMENSION}x{MAX_DIMENSION}.",
                )
        except Exception:
            return False, "Bild konnte nicht gelesen werden."

    return True, None


def sanitize_name(name: str) -> str:
    return name.strip().replace(" ", "_").lower()


# ============================================================
# BOT
# ============================================================
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.guild_expressions = True


class StickerBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        await self.tree.sync()
        print("Slash-Commands synchronisiert.")

    async def on_ready(self):
        print(f"Eingeloggt als {self.user} (ID: {self.user.id})")


bot = StickerBot()
sticker_group = app_commands.Group(name="sticker", description="Verwalte Sticker")


# ============================================================
# /sticker add
# ============================================================
@sticker_group.command(name="add", description="Fuegt einen neuen Sticker hinzu")
@app_commands.describe(
    name="Name des Stickers",
    file="Bilddatei (PNG/APNG/GIF/JPG, max 512 KB)",
)
async def sticker_add(
    interaction: discord.Interaction, name: str, file: discord.Attachment
):
    name = sanitize_name(name)
    ext = os.path.splitext(file.filename)[1].lower()

    if ext not in ALLOWED_EXT:
        await interaction.response.send_message(
            f"Format `{ext}` nicht erlaubt.", ephemeral=True
        )
        return

    data = await file.read()
    ok, err = validate_image(data, ext)
    if not ok:
        await interaction.response.send_message(f"{err}", ephemeral=True)
        return

    success = db_save(
        interaction.guild_id, name, file.filename, data, interaction.user.id
    )
    if not success:
        await interaction.response.send_message(
            f"Sticker `{name}` existiert bereits.", ephemeral=True
        )
        return

    upload_note = ""
    try:
        await interaction.guild.create_sticker(
            name=name,
            description=f"Added by {interaction.user}",
            emoji="\u2b50",
            file=discord.File(io.BytesIO(data), filename=file.filename),
            reason=f"Sticker added by {interaction.user}",
        )
        upload_note = "\nAuch als Server-Sticker registriert."
    except (discord.Forbidden, discord.HTTPException):
        upload_note = "\nNur in Bot-Datenbank gespeichert."

    await interaction.response.send_message(
        f"Sticker `{name}` gespeichert!{upload_note}",
        file=discord.File(io.BytesIO(data), filename=file.filename),
    )


# ============================================================
# /sticker remove
# ============================================================
@sticker_group.command(
    name="remove", description="Loescht einen Sticker (nur Owner/Admin)"
)
@app_commands.describe(name="Name des Stickers")
async def sticker_remove(interaction: discord.Interaction, name: str):
    if not is_owner_or_admin(interaction):
        await interaction.response.send_message(
            "Nur Owner oder Admins duerfen Sticker loeschen.", ephemeral=True
        )
        return

    name = sanitize_name(name)
    if not db_delete(interaction.guild_id, name):
        await interaction.response.send_message(
            f"Kein Sticker `{name}` gefunden.", ephemeral=True
        )
        return

    try:
        for s in interaction.guild.stickers:
            if s.name == name:
                await s.delete(reason=f"Removed by {interaction.user}")
    except (discord.Forbidden, discord.HTTPException):
        pass

    await interaction.response.send_message(
        f"Sticker `{name}` geloescht.", ephemeral=True
    )


# ============================================================
# /sticker list
# ============================================================
@sticker_group.command(name="list", description="Listet alle Sticker auf")
async def sticker_list(interaction: discord.Interaction):
    rows = db_list(interaction.guild_id)
    if not rows:
        await interaction.response.send_message(
            "Keine Sticker vorhanden.", ephemeral=True
        )
        return

    embed = discord.Embed(
        title="Sticker-Uebersicht",
        description=f"{len(rows)} Sticker auf diesem Server:",
        color=discord.Color.blurple(),
    )
    for name, filename, uploaded_by, _uploaded_at in rows[:25]:
        embed.add_field(
            name=f"`{name}`",
            value=f"{filename}\n<@{uploaded_by}>",
            inline=True,
        )
    if len(rows) > 25:
        embed.set_footer(text=f"... und {len(rows) - 25} weitere")

    await interaction.response.send_message(embed=embed)


# ============================================================
# /sticker show
# ============================================================
@sticker_group.command(name="show", description="Zeigt einen bestimmten Sticker an")
@app_commands.describe(name="Name des Stickers")
async def sticker_show(interaction: discord.Interaction, name: str):
    row = db_get(interaction.guild_id, sanitize_name(name))
    if not row:
        await interaction.response.send_message("Nicht gefunden.", ephemeral=True)
        return
    filename, data, _u, _t = row
    await interaction.response.send_message(
        file=discord.File(io.BytesIO(data), filename=filename)
    )


# ============================================================
# /sticker info
# ============================================================
@sticker_group.command(name="info", description="Zeigt Infos zu einem Sticker")
@app_commands.describe(name="Name des Stickers")
async def sticker_info(interaction: discord.Interaction, name: str):
    row = db_get(interaction.guild_id, sanitize_name(name))
    if not row:
        await interaction.response.send_message("Nicht gefunden.", ephemeral=True)
        return
    filename, data, uploaded_by, uploaded_at = row
    embed = discord.Embed(
        title=f"Sticker: `{name}`", color=discord.Color.green()
    )
    embed.add_field(name="Datei", value=filename, inline=True)
    embed.add_field(name="Groesse", value=f"{len(data) / 1024:.1f} KB", inline=True)
    embed.add_field(
        name="Hochgeladen von", value=f"<@{uploaded_by}>", inline=False
    )
    embed.add_field(name="Hochgeladen am", value=str(uploaded_at), inline=False)
    await interaction.response.send_message(
        embed=embed,
        file=discord.File(io.BytesIO(data), filename=filename),
    )


# ============================================================
# /sticker rename
# ============================================================
@sticker_group.command(
    name="rename", description="Benennt einen Sticker um (nur Owner/Admin)"
)
@app_commands.describe(old="Alter Name", new="Neuer Name")
async def sticker_rename(interaction: discord.Interaction, old: str, new: str):
    if not is_owner_or_admin(interaction):
        await interaction.response.send_message(
            "Nur Owner oder Admins.", ephemeral=True
        )
        return
    old, new = sanitize_name(old), sanitize_name(new)
    if not db_rename(interaction.guild_id, old, new):
        await interaction.response.send_message(
            f"Konnte nicht umbenennen. Existiert `{old}`? "
            f"Ist `{new}` schon vergeben?",
            ephemeral=True,
        )
        return
    await interaction.response.send_message(
        f"`{old}` -> `{new}` umbenannt.", ephemeral=True
    )


# ============================================================
# /sticker steal
# ============================================================
@sticker_group.command(
    name="steal", description="Klaut einen Sticker aus einer Nachricht"
)
@app_commands.describe(
    message_id="ID der Nachricht mit dem Sticker", name="Neuer Name"
)
async def sticker_steal(
    interaction: discord.Interaction, message_id: str, name: str
):
    try:
        msg = await interaction.channel.fetch_message(int(message_id))
    except (discord.NotFound, ValueError):
        await interaction.response.send_message(
            "Nachricht nicht gefunden.", ephemeral=True
        )
        return

    if not msg.stickers:
        await interaction.response.send_message(
            "Diese Nachricht enthaelt keinen Sticker.", ephemeral=True
        )
        return

    sticker = msg.stickers[0]
    data = await sticker.read()
    name = sanitize_name(name)
    ext = ".png" if sticker.format == discord.StickerFormatType.png else ".gif"

    ok, err = validate_image(data, ext)
    if not ok:
        await interaction.response.send_message(f"{err}", ephemeral=True)
        return

    saved = db_save(
        interaction.guild_id, name, f"{name}{ext}", data, interaction.user.id
    )
    if not saved:
        await interaction.response.send_message(
            f"`{name}` existiert bereits.", ephemeral=True
        )
        return

    await interaction.response.send_message(
        f"Sticker `{name}` geklaut und gespeichert!",
        file=discord.File(io.BytesIO(data), filename=f"{name}{ext}"),
    )


# ============================================================
# Gruppe registrieren
# ============================================================
bot.tree.add_command(sticker_group)


# ============================================================
# START
# ============================================================
if __name__ == "__main__":
    init_db()
    bot.run(TOKEN)
