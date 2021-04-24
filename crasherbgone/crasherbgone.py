from io import BytesIO
import os
import re
import subprocess
import aiohttp
import discord
import asyncio
from discord.ext.commands.core import guild_only
from discord.mentions import AllowedMentions
from redbot.core import bot, commands, checks, Config
from redbot.core.bot import Red
from typing import Union
from redbot.core import modlog
from redbot.core.modlog import register_casetype, register_casetypes
from subprocess import Popen # its just os with added memes
from redbot.core.data_manager import cog_data_path #For image storage
import secrets



class CrasherBGone(commands.Cog):
    """"I've had it with these motherfucking crashing videos on this motherfucking platform!"""
    default_channel = {
        "enabled" : False
    }
    default_guild = {
        "logtoggle" : False,
        "logmode": "",
        "logchannel": 0,
        "action": ""
    }
    async def initialize(self):
        await self.register_casetypes()


    def __init__(self, bot: "Red"):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=18082006)
        self.config.register_channel(**self.default_channel)
        self.config.register_guild(**self.default_guild)

        async def red_delete_data_for_user(
            self,
            *,
            requester,
            user_id: int,
        ):
            pass # We don't store user data.
            
    @staticmethod
    async def register_casetypes():
        video_crasher_log = {
            "name": "videoclr",
            "default_setting": True,
            "image": "\N{MOVIE CAMERA}",
            "case_str": "Client Crasher",
        }
        try:
            await modlog.register_casetype(**video_crasher_log)
        except RuntimeError:
            pass


    @commands.command(name="crashcheck")
    @guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def _crashcheck(self, ctx, Option: bool, Chan: Union[discord.TextChannel , int] = None):
        """Enable the crash checker in a channel. We'd recommend you only use this in image heavy channels."""
        if Chan == None:
            Chan = ctx.channel
        ChannelConfig = self.config.channel(Chan)
        CurrentStatus = ChannelConfig.enabled()
        if CurrentStatus == True:
            await ChannelConfig.enabled.set(False)
            await ctx.reply("Crash Video checking is disabled within {Chann}".format(Chann=Chan))
        else:
            await ChannelConfig.enabled.set(True)
            await ctx.reply("Crash Video checking is enabled within {Chann}".format(Chann=Chan))

    @commands.group()
    @guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def crcheckadmin(self, ctx):
        """Admin commands for Crash Checker"""

    @crcheckadmin.command(name="togglelog")
    async def _modlogtoggle(self, ctx, Mode: str = None):
        """Toggle whether the modlog is used when a file is deleted. Supported Modes:\n
        ``` ModLog - Logs to Reds Modlog.None\n
        ChannelLog - Enables logging to a channel set in [p]crcheckadmin logchannel\n
        None - Disables Logging.```
        Omit all options to see the current setting.\n
        NOTE - Options are **NOT** case sensitive."""

        LogGuild = self.config.guild(ctx.guild)
        settingsdict = await LogGuild.all()
        TogSetting = settingsdict["logtoggle"]
        TogMode = settingsdict["logmode"]

        if Mode == None:
            await ctx.send("Logging is currently `{status}`(True Means On, False Means Off) `{togglemode}`(You chose the mode, remember!)".format(status=TogSetting, togglemode=TogMode))
            return
        else:
            if Mode.lower() == "modlog":
                await LogGuild.logmode.set("ModLog")
                await LogGuild.logtoggle.set(True)
                await ctx.send("Cases are now going to Red's ModLog. Or I guess, {botname}'s ModLog.".format(botname=ctx.me.name))
                return

            if Mode.lower() == "channellog":
                await LogGuild.logmode.set("ChannelLog")
                await LogGuild.logtoggle.set(True)
                
                LogChannel = settingsdict["logchannel"]
                # except:
                #      LogChannel = None
                if LogChannel == None:
                    await ctx.send("""Incidents will now be going to a defined channel. What that channel is, I don't know, since you **Haven't defined one yet. Please go and do that** - its `{p}crcheckadmin logchannel`""".format(p=ctx.prefix))
                    return
                else:
                    await ctx.send("""Incidents are now being logged to {channel}""".format(channel=LogChannel))
                    return

            if Mode.lower() == "none":
                await LogGuild.logtoggle.set(False)
                await ctx.send("Logging Disabled.")
                return
            else:
                await ctx.send("I think you put an invalid option. Try again, make sure the formatting is correct.")
                return

    @crcheckadmin.command(name="logchannel")
    async def _logchannelset(self, ctx, Channel : discord.TextChannel):
        """Sets the Logging Channel for the `channelog` mode of the.. Log. You ever say log so much it sounds weird?"""
        LogGuild = self.config.guild(ctx.guild)
        settingsdict = await LogGuild.all()
        if Channel == None:
            Channel = ctx.channel
        LogChannelSet = await LogGuild.logchannel.set(Channel.id)
        LogChannelTest = settingsdict["logchannel"]
        try:
            settingsdictUpdate = await LogGuild.all()
            LogChannelSet = await LogGuild.logchannel.set(Channel.id)
            LogChannelTest = settingsdictUpdate["logchannel"]
            await ctx.send("Log Channel set to {id}, {name.mention}".format(id=LogChannelTest, name=self.bot.get_channel(LogChannelTest)))
        except:
            await ctx.send("That might not have been Valid. Try it again with a channel ping, like this: {channel.mention}".format(channel=ctx.channel))
    @crcheckadmin.command(name="action")
    async def _craction(self, ctx, *, Command: str = None):
        """Set a command to be ran on folks who post a crash-link."""
        LogGuild = self.config.guild(ctx.guild)
        settingsdict = await LogGuild.all()

    @commands.Cog.listener()
    async def on_message(self, message):
        ChannelSettingsDict = await self.config.channel(message.channel).all()
        GuildSettingsDict = await self.config.guild(message.channel.guild).all()
        user = message.author
        if user.bot:
            return
        if not message.guild:
            return
        if ChannelSettingsDict["enabled"] != True:
            return
        if not message.attachments: # Gotta check links too!
            escaped = discord.utils.escape_markdown(message.content)
            stripped = escaped.lstrip("\\|")
            stripped2 = stripped.rstrip("|") # Borrowing from gallery a tad
            uris = re.search("(?im)giant.gfycat.com.*mp4", stripped2)
            print(uris)
            if uris != None: #We'll be a bit overzealous and trade it off with this one being calmer.
                            #calmer as in it won't fire an action.
                ModMode = GuildSettingsDict["logtoggle"]
                if ModMode:
                    LogMode = GuildSettingsDict["logmode"]
                    LogChannel = self.bot.get_channel(GuildSettingsDict["logchannel"])
                    if LogMode == "ModLog":
                        case = await modlog.create_case(
                            self.bot, message.channel.guild, message.created_at, action_type="videoclr", user=message.author,
                            moderator=self.bot.user, reason="`giant.gfycat` link that ends in mp4 - I'd recommend checking the link yourself. Content: `{link}`".format(link=message.content))
                        await message.channel.send("Possible Crash Gif deleted, logged, and reported.")
                        await message.delete()

                    if LogMode == "ChannelLog":
                        logchannel = self.bot.get_channel(GuildSettingsDict["logchannel"])
                        await logchannel.send("NOTICE - {twat} has possibly posted a discord crashing gif/mp4.".format(twat=message.user.mention))
                        await logchannel.send("Message Content - {twats_words}".format(twats_words=message.content))
                        await message.delete()
                        await message.channel.send("Possible Crash Gif deleted, logged, and reported.")
                        await message.delete()
                    else:
                        await message.channel.send("possible Crash Gif deleted..")
                        await message.delete()
            #And the next parts feature a bit of stealing from Aiks attempts to do something similar. Hopefully we have more success.
            if message.content.startswith("https://cdn.discordapp.com/attachments/"):
                maybe_url = message.content.split()[0]
                if maybe_url.endswith(".mp4") or maybe_url.endswith(".gif"):
                    await self._video_checker(maybe_url)
        if message.attachments != None: # and now the real fun begins.
            pass
    



    async def _video_checker(self, inputfile): #Yeah Aikaternas File downloader seems to be as good as I'm gonna get, really. mix it in with Popen for bonus points.
        r = secrets.token_hex(6)
        CogPath = f"{cog_data_path(self)}/"
        file_name = f"temp_vid{r}.mp4"
        file_file = f"{CogPath}{file_name}"
        start_frame_file = f"{CogPath}start_frame{r}.jpg"
        end_frame_file = f"{CogPath}end_frame{r}.jpg"

        async with aiohttp.ClientSession() as session:
            async with session.get(inputfile) as resp:
                data = resp.content.read()
                with open(file_file, "wb+") as g:
                    g.write(data)
        try:
            resultSFF = self.bot.loop.run_in_executor(None, subprocess.call(["ffmpeg", "-i", file_file, "-vframes 1", "-q:v 1", f"{start_frame_file}"], timeout=60))
            resultEFF = self.bot.loop.run_in_executor(None, subprocess.call(["ffmpeg", "-sseof -3", "-i", file_file, "-update 1", "-q:v 1", f"{end_frame_file}"], timeout=60))
        except subprocess.TimeoutExpired:
            os.remove(file_file)
            try:
                os.remove(start_frame_file)
            except FileNotFoundError:
                pass
            try:
                os.remove(end_frame_file)
            except FileNotFoundError:
                pass
            return "ERROR"
        # OK so now that we have our two images, its time to probe
        resultEFF.cancel()
        resultSFF.cancel() # make sure they're dead.
        SFFOut = None
        EFFOut = None
        try:
            probeSFF = self.bot.loop.run_in_executor(None, subprocess.call(["ffprobe", "-i", start_frame_file], stdout=SFFOut, timeout=60))
            probeEFF = self.bot.loop.run_in_executor(None, subprocess.call(["ffprobe", "-i", end_frame_file], stdout=EFFOut, timeout=60))
            print(SFFOut)
            print(EFFOut)
        except:
            pass

