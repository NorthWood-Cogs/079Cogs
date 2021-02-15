import discord
import pyscp
from redbot.core import commands
from typing import Optional

from redbot.core.commands import Cog


SCPWiki = pyscp.wikidot.Wiki('scp-wiki.wikidot.com')
ObjectClass = ["Safe", "Euclid", "Keter", "Thaumiel", "Neutralized", "Explained"]
class SCP(commands.Cog):
    """ SCP Cog that utilises an especially adapted wikidot api"""
    def __init__(self, bot):
        self.bot = bot


    @commands.command()
    async def scp(self, ctx, scpID: str):
        """Finds an SCP based on their number. Standard Content warning applies."""
        target = SCPWiki(f'scp-{scpID}')
        PreviewS = target.content
        Preview = PreviewS[:75] + (PreviewS[75:] and '..')
        await ctx.send(f"{Preview}")
        scpEM = discord.Embed(
            titlle=f"{target.title}",
            url=f"{target.url}"

        )


