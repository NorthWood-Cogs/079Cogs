import discord
import pyscp # specifically the one available on PyPi, which links to https://github.com/MrNereof/pyscp/
from redbot.core import commands
from typing import Optional

from redbot.core.commands import Cog


SCPWiki = pyscp.wikidot.Wiki('scp-wiki.wikidot.com')
ObjectClass = ["Safe", "Euclid", "Keter", "Thaumiel", "Neutralized", "Explained"]
class SCP(commands.Cog):
    """ SCP Cog that utilises an especially adapted wikidot api""" # Their Claim, not mine
    def __init__(self, bot):
        self.bot = bot


    def ColourPicker(self, OClass):
        #Basically just a list of If statements because fuck it
        if OClass.lower == "safe":
            return discord.Color.green
        if OClass.lower == "euclid":
            return discord.Color.gold
        if OClass.lower == "keter":
            return discord.Color.red
        if OClass.lower == "thaumiel":
            return discord.Color.blurple
        if OClass.lower == "explained":
            return discord.Color.dark_magenta
        else:
            return discord.Color.greyple


    @commands.command()
    async def scp(self, ctx, scpID: str):
        """Finds an SCP based on their number. Standard Content warning applies.
        Include -j or -ex after the number if it is a joke/explained SCP."""
        target = SCPWiki(f'scp-{scpID}')
        BaseContentText = target.text
        #So by using string finds, we're gonna pick out some useful information
        Content = BaseContentText[:300] + (BaseContentText[300:] and '..')
        #in order - "Preview" is the short text that'll be included, "OC" Will Be Object Class, "Ra" will be Rating.
        Preview = Content[Content.find("Object Class"):]
        PreviewSplit = Preview.split()
        OBJCL = PreviewSplit[0] + PreviewSplit[1] + PreviewSplit[2]
        ClassColour = self.ColourPicker(PreviewSplit[2])
        EmbedContent = Preview.replace(f"{OBJCL}","")
        #TODO So because I like colours we're going to make the embed colour based off the object class
        scpEM = discord.Embed(
            title=f"{target.title}",
            url=f"{target.url}",
            description=f"{EmbedContent}",
            colour=f"{ClassColour}"
        )
        try:
            scpEM.set_thumbnail(url=target.images[0])
        except:
            pass
        await ctx.send(embed=scpEM)
        

