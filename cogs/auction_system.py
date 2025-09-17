import discord
from discord.ext import commands, tasks
from discord import app_commands
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional
import random
import json
import os
from utils.logs.pretty_logs import *
TEST_GUILD_ID = 1220718310455250996
from .pokemons import POKEMONS  # ✅ relative import

DATA_FILE = "auction_data.json"
AUCTION_DURATION = 48 * 60 * 60  # 48h
UPDATE_INTERVAL = 30  # seconds
MAX_BIDS_PER_USER = 6
WHITELIST_ROLE = 1375712535512354898
STARTING_COINS = 1000


def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {"coins": {}, "inventory": {}, "auction": None, "banned": []}


def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)


class AuctionSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.data = load_data()
        self.current_auction_messages = {}  # channel_id -> message
        self.auction_task = None

    # ---------------- Helper Methods ---------------- #

    def is_whitelisted(self, user: discord.Member, guild: discord.Guild) -> bool:
        return (
            user.guild_permissions.administrator
            or any(r.id == WHITELIST_ROLE for r in user.roles)
        )

    def get_balance(self, user_id: int) -> int:
        return self.data["coins"].get(str(user_id), STARTING_COINS)

    def add_balance(self, user_id: int, amount: int):
        uid = str(user_id)
        self.data["coins"][uid] = self.get_balance(user_id) + amount
        save_data(self.data)

    def get_inventory(self, user_id: int):
        return self.data["inventory"].get(str(user_id), [])

    def add_inventory(self, user_id: int, pokemon: str):
        uid = str(user_id)
        if uid not in self.data["inventory"]:
            self.data["inventory"][uid] = []
        self.data["inventory"][uid].append(pokemon)
        save_data(self.data)

    def get_proper_name(self, name: str) -> Optional[str]:
        for p in POKEMONS:
            if p.lower() == name.lower():
                return p
        return None

    # ---------------- Auction Logic ---------------- #

    async def update_current_auction_embed(self, channel: discord.TextChannel):
        while self.data.get("auction"):
            auction = self.data["auction"]
            if not auction:
                break
            embed = discord.Embed(
                title="🏆 Current Auction", color=discord.Color.gold()
            )
            pokemon = auction["pokemon"]
            embed.add_field(name="Pokémon", value=f"**{pokemon}**", inline=False)
            if auction.get("highest_bidder"):
                embed.add_field(
                    name="Highest Bid",
                    value=f"{auction['highest_bid']} coins by <@{auction['highest_bidder']}>",
                    inline=False,
                )
            else:
                embed.add_field(name="Highest Bid", value="No bids yet", inline=False)

            remaining = auction["end_time"] - datetime.now(timezone.utc).timestamp()
            if remaining < 0:
                remaining = 0
            hours, remainder = divmod(int(remaining), 3600)
            minutes, seconds = divmod(remainder, 60)
            embed.set_footer(text=f"Time remaining: {hours}h {minutes}m {seconds}s")

            try:
                msg = self.current_auction_messages.get(channel.id)
                if msg:
                    await msg.edit(embed=embed)
                else:
                    sent_msg = await channel.send(embed=embed)
                    self.current_auction_messages[channel.id] = sent_msg
            except Exception as e:
                print(f"Error updating auction embed: {e}")

            await asyncio.sleep(UPDATE_INTERVAL)

    async def end_auction(self):
        auction = self.data.get("auction")
        if not auction:
            return
        channel = self.bot.get_channel(auction["channel_id"])
        if not isinstance(channel, discord.TextChannel):
            self.data["auction"] = None
            save_data(self.data)
            return

        if auction.get("highest_bidder"):
            winner_id = auction["highest_bidder"]
            pokemon = auction["pokemon"]
            self.add_inventory(winner_id, pokemon)
            await channel.send(
                f"🎉 Auction ended! <@{winner_id}> won **{pokemon}** for {auction['highest_bid']} coins!"
            )
        else:
            await channel.send("❌ Auction ended with no bids.")

        self.data["auction"] = None
        save_data(self.data)
        self.current_auction_messages.pop(channel.id, None)

    # ---------------- Tasks ---------------- #

    @tasks.loop(seconds=10)
    async def check_auction(self):
        auction = self.data.get("auction")
        if not auction:
            return
        if datetime.now(timezone.utc).timestamp() >= auction["end_time"]:
            await self.end_auction()
            # stop the loop safely
            if self.check_auction.is_running():  # type: ignore
                self.check_auction.stop()  # type: ignore

    # ---------------- Commands ---------------- #

    @app_commands.command(name="start_auction", description="Start a new auction")
    @app_commands.guilds(discord.Object(id=TEST_GUILD_ID))
    async def start_auction(self, interaction: discord.Interaction):
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message(
                "❌ This command can only be used in a server.", ephemeral=True
            )
            return
        member = guild.get_member(interaction.user.id)
        if not member or not self.is_whitelisted(member, guild):
            await interaction.response.send_message(
                "❌ Only admins/whitelisted can start.", ephemeral=True
            )
            return
        if self.data.get("auction"):
            await interaction.response.send_message(
                "⚠️ An auction is already running.", ephemeral=True
            )
            return

        pokemon = random.choice(POKEMONS)
        end_time = datetime.now(timezone.utc).timestamp() + AUCTION_DURATION
        self.data["auction"] = {
            "pokemon": pokemon,
            "highest_bid": 0,
            "highest_bidder": None,
            "end_time": end_time,
            "channel_id": interaction.channel_id,
        }
        save_data(self.data)

        await interaction.response.send_message(f"✅ Started auction for **{pokemon}**!")
        if isinstance(interaction.channel, discord.TextChannel):
            asyncio.create_task(
                self.update_current_auction_embed(interaction.channel)
            )
        if not self.check_auction.is_running():  # type: ignore
            self.check_auction.start()  # type: ignore

    @app_commands.command(name="bid", description="Place a bid on the current auction")
    @app_commands.guilds(discord.Object(id=TEST_GUILD_ID))
    async def bid(self, interaction: discord.Interaction, amount: int):
        if interaction.user.id in self.data["banned"]:
            await interaction.response.send_message("❌ You are banned.", ephemeral=True)
            return
        auction = self.data.get("auction")
        if not auction:
            await interaction.response.send_message("❌ No active auction.", ephemeral=True)
            return

        balance = self.get_balance(interaction.user.id)
        if amount > balance:
            await interaction.response.send_message(
                "❌ You don't have enough coins.", ephemeral=True
            )
            return
        if amount <= auction["highest_bid"]:
            await interaction.response.send_message(
                f"⚠️ Your bid must be higher than {auction['highest_bid']}.",
                ephemeral=True,
            )
            return

        # Refund previous bidder
        if auction["highest_bidder"]:
            self.add_balance(auction["highest_bidder"], auction["highest_bid"])

        # Deduct from new bidder
        self.add_balance(interaction.user.id, -amount)
        auction["highest_bid"] = amount
        auction["highest_bidder"] = interaction.user.id
        save_data(self.data)

        await interaction.response.send_message(f"✅ You bid {amount} coins!")
        if isinstance(interaction.channel, discord.TextChannel):
            asyncio.create_task(self.update_current_auction_embed(interaction.channel))

    @app_commands.command(
        name="current_auction", description="Show ongoing auction info"
    )
    @app_commands.guilds(discord.Object(id=TEST_GUILD_ID))
    async def current_auction(self, interaction: discord.Interaction):
        auction = self.data.get("auction")
        if not auction:
            await interaction.response.send_message("❌ No active auction.", ephemeral=False)
            return
        if not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message(
                "❌ Use in a text channel.", ephemeral=True
            )
            return
        await interaction.response.send_message("📊 Current auction info:", ephemeral=False)
        asyncio.create_task(self.update_current_auction_embed(interaction.channel))

    @app_commands.command(name="coins", description="Check your coin balance")
    @app_commands.guilds(discord.Object(id=TEST_GUILD_ID))
    async def coins(self, interaction: discord.Interaction):
        balance = self.get_balance(interaction.user.id)
        await interaction.response.send_message(
            f"💰 You have {balance} coins.", ephemeral=True
        )

    @app_commands.command(name="inventory", description="Show inventory")
    @app_commands.guilds(discord.Object(id=TEST_GUILD_ID))

    async def inventory_cmd(
        self, interaction: discord.Interaction, member: Optional[discord.Member] = None
    ):
        target = member or interaction.user
        inv = self.get_inventory(target.id)
        balance = self.get_balance(target.id)
        embed = discord.Embed(title=f"{target.display_name}'s Inventory", color=discord.Color.blue())
        embed.add_field(name="💰 Coins", value=str(balance), inline=False)
        embed.add_field(name="📦 Pokémon", value=", ".join(inv) if inv else "None", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)


# ---------------- Cog Setup ---------------- #
async def setup(bot: commands.Bot):
    await bot.add_cog(AuctionSystem(bot))

