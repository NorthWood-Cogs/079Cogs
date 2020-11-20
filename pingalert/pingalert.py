import discord
from redbot.core import Config, checks, commands
from redbot.core.utils import common_filters
from redbot.core.bot import Red
from typing import Union
from discord.utils import get

# Shoutout to all my homies that have ZERO grasp of any self-fucking-restraint

class PingAlert(commands.Cog):
    """I hate you all"""

    #Ver. 0.1 - really basic "stop pinging hubert you cunts" version
    #A proper cog comes later. 

    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=412354885235, force_registration=True)
        self.config.register_guild(
            DontPing=[],
            AlertChannel=None
        )
        

    async def red_get_data_for_user(self, *, user_id: int):
        # this cog does not story any data you know the fucking drill
        return {}


    @commands.command()
    async def setchannel(self, ctx, Achannel: discord.TextChannel):
        """Sets the channel for alerting for a ping."""
        guild = ctx.guild
        await self.config.guild(guild).AlertChannel.set(Achannel.id)
        await ctx.send("Done.")

    @commands.Cog.listener()
    async def on_message(self, message):
        user = message.author

        if user.bot:
            return
        if not message.guild:
            return
        if await self.config.guild(message.guild).AlertChannel() is not None:
            god = self.bot.get_user(242306234269696000)
            if god.mentioned_in(message):
                channnnel =  await self.config.guild(message.guild).AlertChannel()
                alertchannel = self.bot.get_channel(channnnel)
                await alertchannel.send(f"{user.mention} ({user.id}) has Pinged Hubert - See {message.jump_url}")
            else:
                return
        else:
            return