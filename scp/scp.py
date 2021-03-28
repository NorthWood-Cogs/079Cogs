import discord
from discord.colour import Color
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
    async def scp(self, ctx,*, scpIDOG: str):
        """Finds an SCP based on their number. Standard Content warning applies.
        Include -j or -ex after the number if it is a joke/explained SCP. Others work too!"""
        scpID = scpIDOG.replace(" ", "")
        if len(scpID) <= 2:
            target = self.SCPWiki(f'scp-{scpID.zfill(3)}')  #pyscp handles the rest
        else:
            target = self.SCPWiki(f'scp-{scpID}')
        try:
            Content = target.text
        except:
            return await ctx.send("This isn't a valid ID, dumbass.")
        #So by using string finds, we're gonna pick out the first "block" of the article
        CaseTag = self.special_cases(scpID) #But this will handle all edge-cases.. Woo...
        ObjectClassFinder = await target.source
        print(self)
        if CaseTag is None:
            embedBack = await self.SCPFinder(scpID=scpID, scpContent=Content, scpTarget=target)
            await ctx.send(embedBack)

    async def SCPFinder(self, scpID, scpContent, scpTarget):
        # And now, to hate myself. hey fun fact, you know Python 3.9 is adding switch statements?
        try:
            ObjectCLStr = scpContent[scpContent.find("Object Class"):]
            ObjectSplit = ObjectCLStr.split()
            OBJCL = ObjectSplit[2]
            ClassColour = await self.ColourPicker(OBJCL)
            print("OB Find")
        except:
            OBJCL = re.search("/(safe|euclid|keter|thaumiel|explained|neutralized)/im", scpTarget.source).group(0)
            ClassColour = await self.ColourPicker(OBJCL)
            print("Regex")
        if OBJCL == None:
            try:
                OBJCL = scpContent[scpContent.find("ADULT CONTENT"):]
                ClassColour = 0x99aab5
                print("AC")
            except: #Ok here we'll do "oh god its fucked"
                OBJCL = str("Can't find an object class!")
                print("error")
                ClassColour = 0x99aab5
        return str(OBJCL)
            
    class GoFuckYourself(Exception):
        pass

        # The wiki has a lot of.. unique cases that the script can't figure out. they go here. If adding to this, please follow the elif format.
    def special_cases(self, ID: str):
        if ID == "2521":
            em = discord.Embed(
                title="●●|●●●●●|●●|●",
                url="http://www.scpwiki.com/scp-2521",
                color=0xe74c3c
            )   
            em.set_image(url="http://scp-wiki.wdfiles.com/local--files/scp-2521/scp_number.jpg")
            return em
        elif ID == "231":
            em = discord.Embed(
                title="SCP-231 - Special Personnel Requirements",
                url="https://scp-wiki.wikidot.com/scp-231",
                color= 0xe74c3c
            )
            em.add_field(name="Object Class",value="Keter",inline=False)
            return em
        elif ID == "000" or ID == "00" or ID == "0": # There's No canon 000. So...
            em = discord.Embed(
                title = "SCP-███ - He he watches us all",
                url = "https://scp-secret-laboratory-wiki.fandom.com/wiki/Hubert_Moszka",
                color = 0xe91e63
            )
            em.add_field(name="Object Class", value="Thaumiel", inline=False)
            em.add_field(name="Help", value="We're trapped in his basement, help!", inline=False)
            em.set_thumbnail(url="https://cdn.discordapp.com/attachments/681599779242770444/817006021276336128/HubS.png")
            return em
        elif ID == "5167":
            em = discord.Embed(
                title="When the imposter is sus",
                url="https://scp-wiki.wikidot.com/scp-5167",
                color=0xe74c3c
            )
            em.set_image(url="https://i.kym-cdn.com/entries/icons/original/000/035/973/cover3.jpg")
            return em

            
