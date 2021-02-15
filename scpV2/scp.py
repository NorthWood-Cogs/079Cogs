import discord
import pyscp
from redbot.core import commands
from typing import Optional

from redbot.core.commands import Cog


SCPWiki = pyscp.wikidot.Wiki('scp-wiki.wikidot.com')
class SCP(commands.Cog):
    """ SCP Cog that utilises an especially adapted wikidot api"""
    def __init__(self, bot):
        self.bot = bot


    @commands.command()
    async def scp(self, ctx, scpID: str):
        """Finds an SCP based on inputted value or common aliases."""
        target = SCPWiki(f'scp-{scpID}')
        await ctx.send(f"{target.title} has a url of {target.url}")


