import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import re
from flask import Flask

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
os.makedirs(DATA_DIR, exist_ok=True)

app = Flask("")


@app.route("/")
def home():
    return "Bot is running!"


# ---------------- BOT SETUP ----------------

intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# ---------------- CONFIG ----------------

SCOREBOARD_FILE = os.path.join(DATA_DIR, "aces_scoreboard.json")
SCOREBOARD_CHANNEL_ID = 1441380119045210255
ALLOWED_ROLES = ["admin", "captains"]

scoreboard_message_id = None


# ---------------- STORAGE ----------------

def load_scoreboard():
    if not os.path.exists(SCOREBOARD_FILE):
        return {"wins": 0, "losses": 0, "map_wins": 0, "map_losses": 0}
    with open(SCOREBOARD_FILE, "r") as f:
        return json.load(f)


def save_scoreboard():
    with open(SCOREBOARD_FILE, "w") as f:
        json.dump(scoreboard_data, f)


scoreboard_data = load_scoreboard()


# ---------------- HELPERS ----------------

def clamp(v):
    return max(0, v)


def has_role(member):
    return any(role.name.lower() in ALLOWED_ROLES for role in member.roles)


def is_admin(member):
    return any(role.name.lower() == "admin" for role in member.roles)


def get_ratio(w, l):
    if l == 0:
        return f"{w:.2f}" if w > 0 else "0"
    return f"{w / l:.2f}"


def get_map_win_percent(mw, ml):
    t = mw + ml
    return "0%" if t == 0 else f"{(mw / t) * 100:.1f}%"


def generate_scoreboard():
    return (
        f"**🏆 UGT Aces's Scoreboard**\n"
        f"Wins: {scoreboard_data['wins']}\n"
        f"Losses: {scoreboard_data['losses']}\n"
        f"W/L Ratio: {get_ratio(scoreboard_data['wins'], scoreboard_data['losses'])}\n"
        f"Map Wins: {scoreboard_data['map_wins']}\n"
        f"Map Losses: {scoreboard_data['map_losses']}\n"
        f"Map Win%: {get_map_win_percent(scoreboard_data['map_wins'], scoreboard_data['map_losses'])}\n"
        f"@everyone"
    )


async def update_scoreboard():
    channel = bot.get_channel(SCOREBOARD_CHANNEL_ID)
    msg = await channel.fetch_message(scoreboard_message_id)
    await msg.edit(content=generate_scoreboard())


# ---------------- EVENTS ----------------

@bot.event
async def on_ready():
    global scoreboard_message_id
    print(f"✅ Logged in as {bot.user}")

    channel = bot.get_channel(SCOREBOARD_CHANNEL_ID)
    async for msg in channel.history(limit=10):
        if msg.author == bot.user and "**🏆 UGT Aces's Scoreboard**" in msg.content:
            scoreboard_message_id = msg.id
            break

    if scoreboard_message_id is None:
        msg = await channel.send(generate_scoreboard())
        scoreboard_message_id = msg.id

    await tree.sync()
    print("✅ Slash commands synced")


# ---------------- TEXT COMMANDS ----------------

@bot.event
async def on_message(message):
    if message.author.bot or not message.guild:
        return

    if not has_role(message.author):
        await bot.process_commands(message)
        return

    content = message.content.strip()
    updated = False

    # ADD
    if content == "Ace+1":
        scoreboard_data["wins"] += 1
        updated = True

    elif content == "Ace-1":
        scoreboard_data["losses"] += 1
        updated = True

    match = re.match(r"^Ace(\d+)-(\d+)$", content, re.IGNORECASE)
    if match:
        a, b = map(int, match.groups())
        scoreboard_data["map_wins"] += a
        scoreboard_data["map_losses"] += b
        scoreboard_data["wins"] += a > b
        scoreboard_data["losses"] += a < b
        updated = True

    # REMOVE
    if content == "-Ace+1":
        scoreboard_data["wins"] = clamp(scoreboard_data["wins"] - 1)
        updated = True

    elif content == "-Ace-1":
        scoreboard_data["losses"] = clamp(scoreboard_data["losses"] - 1)
        updated = True

    remove = re.match(r"^-Ace(\d+)-(\d+)$", content, re.IGNORECASE)
    if remove:
        x, y = map(int, remove.groups())
        scoreboard_data["map_wins"] = clamp(scoreboard_data["map_wins"] - x)
        scoreboard_data["map_losses"] = clamp(scoreboard_data["map_losses"] - y)
        updated = True

    if updated:
        save_scoreboard()
        await update_scoreboard()
        await message.delete()

    await bot.process_commands(message)


# ---------------- SLASH COMMAND GROUP ----------------

aces = app_commands.Group(name="aces", description="Aces scoreboard commands")
tree.add_command(aces)


@aces.command(name="add_maps")
async def add_maps(interaction: discord.Interaction, map_wins: int, map_losses: int):
    if not has_role(interaction.user):
        await interaction.response.send_message("❌ No permission", ephemeral=True)
        return

    scoreboard_data["map_wins"] += map_wins
    scoreboard_data["map_losses"] += map_losses
    scoreboard_data["wins"] += map_wins > map_losses
    scoreboard_data["losses"] += map_wins < map_losses

    save_scoreboard()
    await update_scoreboard()
    await interaction.response.send_message("✅ Match added", ephemeral=True)


@aces.command(name="reset", description="Reset the scoreboard to 0 (Admins only)")
async def reset_scoreboard(interaction: discord.Interaction):
    if not is_admin(interaction.user):
        await interaction.response.send_message(
            "❌ Only admins can reset the scoreboard.",
            ephemeral=True
        )
        return

    scoreboard_data["wins"] = 0
    scoreboard_data["losses"] = 0
    scoreboard_data["map_wins"] = 0
    scoreboard_data["map_losses"] = 0

    save_scoreboard()
    await update_scoreboard()

    await interaction.response.send_message(
        "🧹 **Scoreboard has been reset to 0.**",
        ephemeral=True
    )


def keep_alive():
    from threading import Thread
    t = Thread(target=app.run, kwargs={"host": "0.0.0.0", "port": 8000})
    t.start()


keep_alive()
bot.run(os.getenv("DISCORD_TOKEN"))