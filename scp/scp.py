import discord
from discord.errors import Forbidden, HTTPException
import pyscp # Installed On Cog install, using https://github.com/NorthWood-Cogs/pyscp
import re
import asyncio
import os

from redbot.core import commands, Config, data_manager
from typing import Optional
from redbot.core.commands import Cog


ObjectClass = ["Safe", "Euclid", "Keter", "Thaumiel", "Neutralized", "Explained"]
class SCP(commands.Cog):
    """ SCP Cog that utilises an especially adapted wikidot api""" # Their Claim, not mine
    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier="3957890832758296589023290568043")
        self.config.register_global(
                isthisjustawayofsavingmytime=True,
                configLocation=str(data_manager.cog_data_path(self) / "scp.db")
        )
        self.SCPWiki = pyscp.wikidot.Wiki('scp-wiki.wikidot.com')
        #try:
            #confLoc = str(self.config.configLocation())
            #self.SCPWiki = pyscp.snapshot.Wiki('scp-wiki.wikidot.com', confLoc)
        #except:
            #self.SCPWIki = pyscp.wikidot.Wiki('scp-wiki.wikidot.com')
            #print("WARNING - DB Not Found! This cog will be slower!")
            
    

    async def ColourPicker(self, OClass):
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
        Include -j or -ex after the number if it is a joke/explained SCP. Others work too!"""
        target = self.SCPWiki(f'scp-{scpID}')  #pyscp handles the rest
        Content = target.text
        #So by using string finds, we're gonna pick out the first "block" of the article
        ObjectClassFinder = await target.source #I hate their templates, this is the workaround.
        try:
            #now, the problem with our method is that it creates A LOT of ways for it to go wrong. so lets prepare for that.
            #We'll firstly gleam it for an object Class - Safe, Euclid, etc... and also the corresponding Colour.
            #Sorta Cute you'd think its easy. The issue with the wiki is one of inconsistent formatting and names - so we'll need to encounter for banner styles where possible
            #Now that ObjectClassFinder is Making sense, eh?
            # and so, i bring to you the triple-try-that-probably-doesn't-need-to-be-this-way-loop. Run.
            try:
                ObjectCLStr = Content[Content.find("Object Class"):]
                ObjectSplit = ObjectCLStr.split() #This will (try) to find a string
                OBJCL = ObjectSplit[2]
                ClassColour = await self.ColourPicker(OBJCL)
            except:
                try:
                    OBJCL = re.search("/safe|euclid|keter|thaumiel|explained|neutralized/im", ObjectClassFinder).group()
                    ClassColour = await self.ColourPicker(OBJCL)
                # the less neat way...
                except:
                    OBJCL = "Failed to Obtain Object Class..."
                    ClassColour = 0x99aab5 
        #Then, we'll attempt to grab the Special Containment Procedures in a similar manner.
            try:
                SpeConProStr = Content[Content.find("Special Containment Procedures"):Content.find("Description")]
                ContainmentInfo = " ".join(SpeConProStr.split(" ")[3:])
                ContainmentToEmbed = ContainmentInfo[:1000] + (ContainmentInfo[1000:] and '...')
                #Instead of splitting like last time, this time we'll join off a split for the fun of it.
            except:
                ContainmentToEmbed = "Couldn't obtain the Containment Procedure..."

            errors = ""
        except:
            errors = "There was some trouble obtaining some information. Typically, this is due to an archive warning - the Link should work fine to open the real article."
            ClassColour = self.ColourPicker("Keked") #Greyple in case it all goes wrong

        scpEM = discord.Embed(
            title=f"{target.title}",
            url=f"{target.url}", #We're not really including a lot in the base embed (NOTE to self do I want a footer?) 
            colour=ClassColour,     # Since we want custom fields for the formatting.
        )
        try: #as all this is, technically, not required, so it gets its own try loop. THE ORDER HERE IS IMPORTANT!
            OBJCCL = OBJCL.capitalize()
            scpEM.add_field(name="Object Class",value=f"{OBJCCL}",inline=False)
            scpEM.add_field(name="Special Containment Procedures", value=f"{ContainmentToEmbed}",inline=False)
            scpEM.set_thumbnail(url=target.images[0]) #THUMBNAIL must ALWAYS be last, as not every page has an image attached
        except:
            pass
        try:
            await ctx.send(f"{errors}",embed=scpEM)
        except HTTPException(Forbidden):
            try:
                await ctx.send("I can't send embeds here! Probably")
            except: pass

        



        ### THE FOLLOWING is retired code from an old idea to store a local copy of the wiki.
        ### Turns out its fairly large; storage would be impractical to a fair few folks.
        ### Good Job I hadn't finished this up then, huh..

    # async def UpdateDB(self):
    #     configLocation = str(data_manager.cog_data_path(self) / "scp.db")
    #     BaseWiki = pyscp.wikidot.Wiki('scp-wiki.wikidot.com')
    #     snapshotToMake = pyscp.snapshot.SnapshotCreator(configLocation)
    #     await snapshotToMake.take_snapshot(BaseWiki, forums=False)
    #     return "Finished."
    #     #NOTE - THIS WILL TAKE SOME TIME.


    # @commands.is_owner()
    # @commands.command()
    # async def DBCreate(self, ctx):
    #     """Creates a local DB of the SCP wiki"""
    #     await ctx.send("Now Creating a local copy, This WILL take some time.")
    #     try:
    #         loop = asyncio.get_running_loop()
    #         taske = loop.create_task(self.UpdateDB())
    #         loop.run_forever(taske)
    #     finally:
    #         loop.close()
        
    #     await ctx.send(f"DB download Completed, {ctx.author.mention}. Please reload the cog.")
