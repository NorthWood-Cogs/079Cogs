from logging import error
import os
import re
import sys
import subprocess
import aiohttp
import discord
import asyncio
import aiofiles
from discord.ext.commands.core import guild_only
from redbot.core import bot, commands, checks, Config
from redbot.core.bot import Red
from typing import Union
from redbot.core import modlog
from redbot.core.modlog import register_casetype, register_casetypes
from redbot.core.data_manager import cog_data_path  # For image storage
import secrets

content_types_to_check = {
    "embeds": [
        "gifv",
        "video",
    ],
    "attachements": [
        "video/mp4",
        "image/gif",
    ],
    "links": [],

}

class CrasherBGone(commands.Cog):
    """"I've had it with these motherfucking crashing videos on this motherfucking platform!"""
    default_channel = {
        "enabled": False
    }
    default_guild = {
        "logtoggle": False,
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
            pass  # We don't store user data.

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
    async def _crashcheck(self, ctx, Option: bool, Chan: Union[discord.TextChannel, int] = None):
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
            await ctx.send(
                "Logging is currently `{status}`(True Means On, False Means Off) `{togglemode}`(You chose the mode, remember!)".format(
                    status=TogSetting, togglemode=TogMode))
            return
        else:
            if Mode.lower() == "modlog":
                await LogGuild.logmode.set("ModLog")
                await LogGuild.logtoggle.set(True)
                await ctx.send(
                    "Cases are now going to Red's ModLog. Or I guess, {botname}'s ModLog.".format(botname=ctx.me.name))
                return

            elif Mode.lower() == "channellog":
                await LogGuild.logmode.set("ChannelLog")
                await LogGuild.logtoggle.set(True)

                LogChannel = settingsdict["logchannel"]
                # except:
                #      LogChannel = None
                if LogChannel == None:
                    await ctx.send(
                        """Incidents will now be going to a defined channel. What that channel is, I don't know, since you **Haven't defined one yet. Please go and do that** - its `{p}crcheckadmin logchannel`""".format(
                            p=ctx.prefix))
                    return
                else:
                    await ctx.send("""Incidents are now being logged to {channel}""".format(channel=LogChannel))
                    return

            elif Mode.lower() == "none":
                await LogGuild.logtoggle.set(False)
                await ctx.send("Logging Disabled.")
                return
            else:
                await ctx.send("I think you put an invalid option. Try again, make sure the formatting is correct.")
                return

    @crcheckadmin.command(name="logchannel")
    async def _logchannelset(self, ctx, Channel: discord.TextChannel):
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
            await ctx.send("Log Channel set to {id}, {name.mention}".format(id=LogChannelTest,
                                                                            name=self.bot.get_channel(LogChannelTest)))
        except:
            await ctx.send(
                "That might not have been Valid. Try it again with a channel ping, like this: {channel.mention}".format(
                    channel=ctx.channel))

    @crcheckadmin.command(name="action")
    async def _craction(self, ctx, *, Command: str = None):
        """Set a command to be ran on folks who post a crash-link."""
        LogGuild = self.config.guild(ctx.guild)
        settingsdict = await LogGuild.all()



    @commands.Cog.listener()
    async def on_message(self, msg):
        ChannelSettingsDict = await self.config.channel(msg.channel).all()
        GuildSettingsDict = await self.config.guild(msg.channel.guild).all()

        if msg.author.bot or not msg.guild or not ChannelSettingsDict["enabled"]: return

        await msg.channel.send(f"atts: {len(msg.attachments)}|embs: {len(msg.embeds)}")
        s1 = ", ".join(att.content_type for att in msg.attachments)
        s2 = ", ".join(emb.type for emb in msg.embeds)
        await msg.channel.send(f"Types: {s1}, {s2}")

        if msg.attachments:
            await self.attachments_check(msg)
        if msg.embeds:
            await self.embed_check(msg)
        #await self.link_check(msg) Depreciated

    async def attachments_check(self, msg):
        GuildSettingsDict = await self.config.guild(msg.channel.guild).all()

        for attachement in msg.attachments:
            content_type = attachement.content_type

            if content_type in content_types_to_check["attachements"]:
                await self.send_info_and_handle_message(msg, 1)
                ... #Handle the attachement

    async def embed_check(self, msg):
        GuildSettingsDict = await self.config.guild(msg.channel.guild).all()

        for embed in msg.embeds:
            content_type = embed.type

            if content_type in content_types_to_check["embeds"]:
                await self.send_info_and_handle_message(msg, 2)
                ... #Handle the attachement

    async def link_check(self, msg):
        ChannelSettingsDict = await self.config.channel(msg.channel).all()
        GuildSettingsDict = await self.config.guild(msg.channel.guild).all()

        escaped = discord.utils.escape_markdown(msg.content)
        stripped = escaped.lstrip("\\|")
        stripped2 = stripped.rstrip("|") # Borrowing from gallery a tad
        uris = re.search("(?im)giant.gfycat.com.*mp4", stripped2)
        print(uris)
        if uris != None: #We'll be a bit overzealous and trade it off with this one being calmer.
            #calmer as in it won't fire an action.
            await self.send_info_and_handle_message(msg)

    async def send_info_and_handle_message(self, msg, type:int):
        """

        :param msg:
        :param type: 1=attachement, 2=embed, 3=link
        :return:
        """
        def type_to_text(type:int):
            if type==1: return "attachement"
            elif type==2: return "embed"
            elif type==3: return "link"

        def type_to_link(type:int, msg):
            if type==1: return ", ".join(attachment.url for attachment in msg.attachments)
            elif type==2: return ", ".join(embed.url for embed in msg.embeds)
            elif type==3: return "link"


        GuildSettingsDict = await self.config.guild(msg.channel.guild).all()
        ModMode = GuildSettingsDict["logtoggle"]
        if ModMode:
            LogMode = GuildSettingsDict["logmode"]
            LogChannel = self.bot.get_channel(GuildSettingsDict["logchannel"])
            if LogMode == "ModLog":
                case = await modlog.create_case(
                    self.bot, msg.channel.guild, msg.created_at, action_type="videoclr", user=msg.author,
                    moderator=self.bot.user,
                    reason=f"`Crasher detected in message's {type_to_text(type)}` - Link yourself. Content: `{type_to_link(type, msg)}`"
                        .format(link=msg.content))
                await msg.channel.send("Possible Crash Gif deleted, logged, and reported.")
                await msg.delete()

            if LogMode == "ChannelLog":
                logchannel = self.bot.get_channel(GuildSettingsDict["logchannel"])
                await logchannel.send(f"NOTICE - {msg.author.mention} has possibly posted a discord crashing gif/mp4 via {type_to_text(type)}.")
                if(type == 1): await logchannel.send(f"Attachement in question: {type_to_link(type, msg)}")
                await logchannel.send("Message Content - {twats_words}".format(twats_words=msg.content))
                await msg.delete()
                await msg.channel.send("Possible Crash Gif deleted, logged, and reported.")
                await msg.delete()
            else:
                await msg.channel.send("possible Crash Gif deleted..")
                await msg.delete()

    async def _video_checker(self, inputfile):  # Borrowing from Aik and Zeph to try and get this to work
        r = secrets.token_hex(6)
        CogPath = f"{cog_data_path(self)}/"
        print(CogPath)
        file_name = f"temp_vid{r}.mp4"
        print(file_name)
        file_file = f"{CogPath}{file_name}"
        print(file_file)
        start_frame_file = f"{CogPath}start_frame{r}.txt"
        print(start_frame_file)
        end_frame_file = f"{CogPath}end_frame{r}.txt"

        async with aiohttp.ClientSession() as session:
            async with session.get(inputfile) as resp:
                if resp.status == 200:
                    f = await aiofiles.open(file_file, mode="wb+")
                    await f.write(await resp.read())
                    print(f"File Downloaded.")
                    await f.close()

        print(file_file)
        await asyncio.sleep(5)
        EFF = await asyncio.create_subprocess_exec(f"ffmpeg -i {file_file} -vframes 1 -q:v 1 {start_frame_file}")

        # OK so now that we have our two images, its time to probe


"""
Credits to:
    u/LMGN
    https://www.reddit.com/r/discordapp/comments/khuu1r/how_to_avoid_the_discord_crashing_video/
"""
