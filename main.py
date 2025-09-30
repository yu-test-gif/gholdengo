# main.py
import os
import asyncio
import discord
from discord.ext import commands
from discord import app_commands

from Constants.variables import DEFAULT_GUILD_ID, DATA_DIR
from pretty_logs import pretty_log

# ---- Intents / Bot ----
intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix=";", intents=intents)

# ---- Simple health check command ----
@bot.tree.command(name="ping_test", description="Check if the bot is alive")
@app_commands.guilds(discord.Object(id=DEFAULT_GUILD_ID))
async def ping_test(interaction: discord.Interaction):
    await interaction.response.send_message("🏓 Pong!", ephemeral=True)

# ---- Lifecycle ----
@bot.event
async def on_ready():
    # Guard for type checker: bot.user may be Optional
    user = bot.user
    if user is None:
        pretty_log("info", "Bot is online (user not yet cached).")
    else:
        pretty_log("info", f"Bot online as {user} (ID: {user.id})")

    try:
        # Fast guild-only sync
        await bot.tree.sync(guild=discord.Object(id=DEFAULT_GUILD_ID))
        pretty_log("info", f"Slash commands synced to guild {DEFAULT_GUILD_ID}")
    except Exception as e:
        pretty_log("error", f"Slash sync failed: {e}")

    try:
        await bot.change_presence(activity=discord.Game(name="/auction_list • /auction_bid"))
    except Exception:
        pass

# ---- Boot ----
async def main():
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
    except Exception:
        pass

    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise RuntimeError("❌ DISCORD_TOKEN environment variable is not set.")

    try:
        await bot.load_extension("cogs.auctions")
        pretty_log("info", "Loaded extension: cogs.auctions")
    except Exception as e:
        pretty_log("error", f"Failed to load cogs.auctions: {e}")
        raise

    await bot.start(token)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pretty_log("info", "Shutting down...")
