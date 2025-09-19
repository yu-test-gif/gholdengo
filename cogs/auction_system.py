    # cogs/auction_system.py

    import discord
    from discord import app_commands
    from discord.ext import commands, tasks
    import asyncio
    import json
    import os
    from typing import Optional

    from .pokemons import POKEMONS  # your pokemon list
    from utils.logs.pretty_logs import pretty_log

    DATA_FILE = "auction_data.json"
    UPDATE_INTERVAL = 15  # seconds for embed updates


    def load_data():
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, "r") as f:
                return json.load(f)
        return {
            "coins": {},
            "inventory": {},
            "auction": None,
            "banned": []
        }


    def save_data(data):
        with open(DATA_FILE, "w") as f:
            json.dump(data, f, indent=4)


    class AuctionSystem(commands.Cog):
        def __init__(self, bot: commands.Bot):
            self.bot = bot
            self.data = load_data()
            self.current_auction_messages: dict[int, discord.Message] = {}
            self.auction_update_task = None

        # -------------------- Helpers -------------------- #

        def get_balance(self, user_id: int) -> int:
            return self.data["coins"].get(str(user_id), 1000)

        def add_balance(self, user_id: int, amount: int):
            uid = str(user_id)
            self.data["coins"][uid] = self.get_balance(user_id) + amount
            save_data(self.data)

        def add_inventory(self, user_id: int, pokemon: str):
            uid = str(user_id)
            if uid not in self.data["inventory"]:
                self.data["inventory"][uid] = []
            self.data["inventory"][uid].append(pokemon)
            save_data(self.data)

        def get_inventory(self, user_id: int):
            return self.data["inventory"].get(str(user_id), [])

        def is_banned(self, user_id: int) -> bool:
            return str(user_id) in self.data.get("banned", [])

        def _is_whitelisted_member(self, member: discord.Member) -> bool:
            if not member:
                return False
            return member.guild_permissions.administrator or member.roles and any(
                r.id == 1375712535512354898 for r in member.roles
            )

        # -------------------- Auction Embed -------------------- #

        async def update_auction_embed(self, channel: discord.TextChannel):
            auction = self.data.get("auction")
            if not auction or not isinstance(channel, discord.TextChannel):
                return

            embed = discord.Embed(
                title="🏆 Current Auction",
                description=f"Pokémon: **{auction['pokemon']}**",
                color=discord.Color.gold()
            )

            highest_bid = auction.get("highest_bid", 0)
            bidder_id = auction.get("highest_bidder")
            if bidder_id:
                member = channel.guild.get_member(bidder_id)
                bidder_name = member.display_name if member else f"<@{bidder_id}>"
            else:
                bidder_name = "No bids yet"

            embed.add_field(name="Highest Bid", value=f"{highest_bid} coins\nBidder: {bidder_name}", inline=False)
            remaining = max(0, int(auction.get("end_time", 0) - asyncio.get_event_loop().time()))
            minutes, seconds = divmod(remaining, 60)
            embed.set_footer(text=f"Time remaining: {minutes}m {seconds}s")

            # edit existing message or send new
            msg = self.current_auction_messages.get(channel.id)
            try:
                if msg:
                    await msg.edit(embed=embed)
                else:
                    sent_msg = await channel.send(embed=embed)
                    self.current_auction_messages[channel.id] = sent_msg
            except Exception as e:
                pretty_log("error", f"Failed updating auction embed: {e}")

        async def auction_loop(self):
            while True:
                auction = self.data.get("auction")
                if auction:
                    channel = self.bot.get_channel(auction.get("channel_id"))
                    if isinstance(channel, discord.TextChannel):
                        await self.update_auction_embed(channel)
                    # check if auction ended
                    if asyncio.get_event_loop().time() >= auction.get("end_time", 0):
                        await self.end_auction()
                await asyncio.sleep(UPDATE_INTERVAL)

        async def end_auction(self):
            auction = self.data.get("auction")
            if not auction:
                return

            channel = self.bot.get_channel(auction.get("channel_id"))
            if isinstance(channel, discord.TextChannel):
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
            if channel and channel.id in self.current_auction_messages:
                self.current_auction_messages.pop(channel.id)

        # -------------------- Slash Commands -------------------- #

        @app_commands.command(name="ping_test", description="Check if slash commands work")
        @app_commands.guilds(discord.Object(id=DEFAULT_GUILD_ID))
        async def ping_test(self, interaction: discord.Interaction):
            await interaction.response.send_message("✅ Slash commands are working!")

        @app_commands.command(name="coins", description="Check your coin balance")
        @app_commands.guilds(discord.Object(id=DEFAULT_GUILD_ID))
        async def coins(self, interaction: discord.Interaction):
            await interaction.response.send_message(f"💰 You have {self.get_balance(interaction.user.id)} coins.", ephemeral=True)

        @app_commands.command(name="inventory", description="Show inventory")
        @app_commands.guilds(discord.Object(id=DEFAULT_GUILD_ID))
        async def inventory_cmd(self, interaction: discord.Interaction, member: Optional[discord.Member] = None):
            target = member or interaction.user
            inv = self.get_inventory(target.id)
            balance = self.get_balance(target.id)
            embed = discord.Embed(title=f"{target.display_name}'s Inventory", color=discord.Color.blue())
            embed.add_field(name="💰 Coins", value=str(balance), inline=False)
            embed.add_field(name="📦 Pokémon", value=", ".join(inv) if inv else "None", inline=False)
            await interaction.response.send_message(embed=embed, ephemeral=True)

        @app_commands.command(name="auction_start", description="Start global auction")
        @app_commands.guilds(discord.Object(id=DEFAULT_GUILD_ID))
        async def auction_start(self, interaction: discord.Interaction):
            if not isinstance(interaction.channel, discord.TextChannel):
                await interaction.response.send_message("❌ Use in text channel only.", ephemeral=True)
                return
            member = interaction.guild.get_member(interaction.user.id) if interaction.guild else None
            if not self._is_whitelisted_member(member):
                await interaction.response.send_message("❌ You are not whitelisted.", ephemeral=True)
                return
            if self.data.get("auction"):
                await interaction.response.send_message("⚠️ Auction already running.", ephemeral=True)
                return

            pokemon = POKEMONS[0]  # pick first for demo, can randomize
            end_time = asyncio.get_event_loop().time() + 60  # 1 minute for demo
            self.data["auction"] = {
                "pokemon": pokemon,
                "highest_bid": 0,
                "highest_bidder": None,
                "end_time": end_time,
                "channel_id": interaction.channel.id
            }
            save_data(self.data)
            await interaction.response.send_message(f"✅ Started auction for **{pokemon}**!")
            if not self.auction_update_task:
                self.auction_update_task = asyncio.create_task(self.auction_loop())

        # -------------------- BID COMMAND -------------------- #
        @app_commands.command(name="bid", description="Place a bid")
        @app_commands.guilds(discord.Object(id=DEFAULT_GUILD_ID))
        async def bid(self, interaction: discord.Interaction, amount: int):
            if self.is_banned(interaction.user.id):
                await interaction.response.send_message("❌ You are banned.", ephemeral=True)
                return
            auction = self.data.get("auction")
            if not auction:
                await interaction.response.send_message("❌ No active auction.", ephemeral=True)
                return

            if amount <= auction.get("highest_bid", 0):
                await interaction.response.send_message(f"⚠️ Bid must be higher than {auction['highest_bid']}.", ephemeral=True)
                return
            if amount > self.get_balance(interaction.user.id):
                await interaction.response.send_message("❌ Not enough coins.", ephemeral=True)
                return

            # Refund previous
            if auction.get("highest_bidder"):
                self.add_balance(auction["highest_bidder"], auction["highest_bid"])

            # Deduct new bidder
            self.add_balance(interaction.user.id, -amount)
            auction["highest_bid"] = amount
            auction["highest_bidder"] = interaction.user.id
            save_data(self.data)

            await interaction.response.send_message(f"✅ You bid {amount} coins!")
            channel = interaction.channel if isinstance(interaction.channel, discord.TextChannel) else None
            if channel:
                await self.update_auction_embed(channel)

        # -------------------- OTHER ADMIN COMMANDS -------------------- #
        @app_commands.command(name="give_coins", description="Give/subtract coins to a player")
        @app_commands.guilds(discord.Object(id=DEFAULT_GUILD_ID))
        async def give_coins(self, interaction: discord.Interaction, member: discord.Member, amount: int):
            if not self._is_whitelisted_member(member):
                await interaction.response.send_message("❌ Not whitelisted.", ephemeral=True)
                return
            self.add_balance(member.id, amount)
            await interaction.response.send_message(f"✅ {member.display_name} now has {self.get_balance(member.id)} coins.")

        # ... continue implementing the rest like /give_all, /yeet, /check, /reset_auction
        # in same pattern with @app_commands.guilds(discord.Object(id=DEFAULT_GUILD_ID))

    # -------------------- Setup Cog -------------------- #
    async def setup(bot: commands.Bot):
        await bot.add_cog(AuctionSystem(bot))