import asyncio
import discord
import re

from redbot.core import Config, checks, commands
from redbot.core.utils import common_filters

from redbot.core.bot import Red
from typing import Literal

class Gallery(commands.Cog):
    """
    Gallery channels!
    """

    __author__ = "saurichable, [Edit's] Sinon"
    __version__ = "1.2.1.E"

    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(
            self, identifier=564154651321346431, force_registration=True
        )

        self.config.register_guild(channels=[], whitelist=None, time=0)
        
    async def red_get_data_for_user(self, *, user_id: int):
        # this cog does not story any data
        return {}
    
    async def red_delete_data_for_user(
        self,
        *,
        requester: Literal["discord_deleted_user", "owner", "user", "user_strict"],
        user_id: int,
    ):
        
        pass # We Do nothing with user data here, so, No but have a fox gif insted 🦊- https://thumbs.gfycat.com/HarmoniousFrailKissingbug-size_restricted.gif.

    @commands.command()
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    @checks.bot_has_permissions(manage_messages=True)
    async def addgallery(self, ctx: commands.Context, channel: discord.TextChannel):
        """Add a channel to the list of Gallery channels."""
        if channel.id not in await self.config.guild(ctx.guild).channels():
            async with self.config.guild(ctx.guild).channels() as channels:
                channels.append(channel.id)
            await ctx.send(
                f"{channel.mention} has been added into the Gallery channels list."
            )
        else:
            await ctx.send(
                f"{channel.mention} is already in the Gallery channels list."
            )

    @commands.command()
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    @checks.bot_has_permissions(manage_messages=True)
    async def rmgallery(self, ctx: commands.Context, channel: discord.TextChannel):
        """Remove a channel from the list of Gallery channels."""
        if channel.id in await self.config.guild(ctx.guild).channels():
            async with self.config.guild(ctx.guild).channels() as channels:
                channels.remove(channel.id)
            await ctx.send(
                f"{channel.mention} has been removed from the Gallery channels list."
            )
        else:
            await ctx.send(
                f"{channel.mention} already isn't in the Gallery channels list."
            )

    @commands.command()
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    @checks.bot_has_permissions(manage_messages=True)
    async def galleryrole(self, ctx: commands.Context, role: discord.Role = None):
        """Add a whitelisted role."""
        if not role:
            await self.config.guild(ctx.guild).whitelist.set(None)
            await ctx.send(f"Whitelisted role has been deleted.")
        else:
            await self.config.guild(ctx.guild).whitelist.set(role.id)
            await ctx.send(f"{role.name} has been whitelisted.")

    @commands.command()
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    @checks.bot_has_permissions(manage_messages=True)
    async def gallerytime(self, ctx: commands.Context, time: int):
        """Set how long (in seconds!!) the bot should wait before deleting non images.
        
        0 to reset (default time)"""
        await self.config.guild(ctx.guild).time.set(time)
        await ctx.send(
            f"I will wait {time} seconds before deleting messages that are not images."
        )

    @commands.Cog.listener()
    async def on_message(self, message):
        user = message.author
        if user.bot:
            return
        if not message.guild:
            return
        if message.channel.id not in await self.config.guild(message.guild).channels():
            return
        if not message.attachments:
            escaped = discord.utils.escape_markdown(message.content)
            stripped = escaped.lstrip("\\|")
            stripped2 = stripped.rstrip("|") # Spoiler bullS**t handling. Who knew that two lines 
            uris = re.findall(
                "(?=\S+youtube\.com|\S+youtu\.be\/|\S+tenor\.com|\S+\.mov|\S+\.jpg|\S+\.jpeg|\S+\.tiff|\S+\.gif|\S+\.bmp|\S+\.mp4|\S+\.webm|\S+\.png|)((?<!\S)(((f|ht){1}tp[s]?:\/\/+|(?<!\S)www\.)[-a-zA-Z0-9@:%_\+.~#?&|\/\/=]+))",
                stripped,
            )
            if len(uris) == 1:
                uri = "".join(uris)
                uri = uri.split("?")[0]
                parts = uri.split(".")
                extension = parts[-1]
                imageTypes = ["jpg", "jpeg", "tiff", "png", "gif", "bmp", "mp4", "webm", "mov"]
                if extension in imageTypes:
                    return
            rid = await self.config.guild(message.guild).whitelist()
            time = await self.config.guild(message.guild).time()
            if rid:
                role = message.guild.get_role(int(rid))
                if role:
                    if role in message.author.roles:
                        return
            if time != 0:
                await asyncio.sleep(time)
            await message.delete()
