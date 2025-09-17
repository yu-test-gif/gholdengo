import asyncio
import os

import discord
from discord.ext import commands

DEFAULT_GUILD_ID = 841888736559628298

from keep_alive import keep_alive

from utils.logs.pretty_logs import *

# --- Configuration ---
GUILD_ID = DEFAULT_GUILD_ID

# --- Intents ---
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

# --- Bot setup ---
bot = commands.Bot(command_prefix="!", intents=intents)
set_ghouldengo_bot(bot=bot)


# --- on_ready event ---
@bot.event
async def on_ready():
    pretty_log("info", f"Bot is online as {bot.user}")

    # Sync slash commands for your guild
    try:
        guild = discord.Object(id=GUILD_ID)
        synced = await bot.tree.sync(guild=guild)
        pretty_log("info", f"Synced {len(synced)} guild commands to {guild.id}")
    except Exception as e:
        pretty_log("error", f"Error syncing slash commands: {e}")


# --- Test slash command ---
@bot.tree.command(name="ping_test", description="Check if slash commands work")
async def ping_test(interaction: discord.Interaction):
    await interaction.response.send_message("✅ Slash commands are working!")


# --- Load cogs ---
async def load_cogs():
    try:
        await bot.load_extension("cogs.auction_system")
        pretty_log("info", "Loaded cog: cogs.auction_system")
    except Exception as e:
        pretty_log("error", f"Failed to load cog: {e}")


# --- Start bot ---
async def main():
    keep_alive()
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise ValueError("❌ DISCORD_TOKEN environment variable not set!")

    async with bot:
        await load_cogs()
        pretty_log("info", "Starting bot with token...")

        await bot.start(token)


if __name__ == "__main__":
    asyncio.run(main())
