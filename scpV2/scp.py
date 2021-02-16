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
        if OClass.lower() == "safe":
            return 0x2ecc71 #Green
        if OClass.lower() == "euclid":
            return 0xf1c40f #Gold
        if OClass.lower() == "keter":
            return 0xe74c3c #Red
        if OClass.lower() == "thaumiel":
            return 0x3498db #Blue
        if OClass.lower() == "explained":
            return 0xe91e63 #Magenta
        else:
            return 0x99aab5 #Greyple


    @commands.command()
    async def scp(self, ctx, scpID: str):
        """Finds an SCP based on their number. Standard Content warning applies.
        Include -j or -ex after the number if it is a joke/explained SCP."""
        target = SCPWiki(f'scp-{scpID}')
        BaseContentText = target.text
        #So by using string finds, we're gonna pick out some useful information
        Content = BaseContentText[:800] + (BaseContentText[800:] and '..')
        #in order - "Preview" is the short text that'll be included, "OC" Will Be Object Class, "Ra" will be Rating.
        Preview = Content[Content.find("Object Class"):]
        PreviewSplit = Preview.split()
        try:
            OBJCL = PreviewSplit[2]
            ClassColour = self.ColourPicker(PreviewSplit[2])
            EmbedContent = ' '.join(Preview.Split(' ')[6:]) # Annoyingly, the OBJCL split can't seem to be used here. I tried.
            errors = ""
        except:
            EmbedContent = Preview
            errors = "There was some trouble obtaining some information. Typically, this is due to an archive warning - the Link should work fine to open the real article."
            ClassColour = 0x99aab5 #Greyple in case it all goes wrong

        #TODO So because I like colours we're going to make the embed colour based off the object class
        scpEM = discord.Embed(
            title=f"{target.title}",
            url=f"{target.url}",
            colour=ClassColour,
        )
        try:
            scpEM.set_thumbnail(url=target.images[0])
            scpEM.add_field(name="Object Class",value=f"{OBJCL}",inline=False)
            scpEM.add_field(name="Special Containment Procedures", value=f"{EmbedContent}",inline=False)
        except:
            pass
        await ctx.send(f"{errors}",embed=scpEM)
        

