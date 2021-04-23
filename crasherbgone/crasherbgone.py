import discord
import asyncio
from redbot.core import bot, commands, checks, Config
from typing import Union
from redbot.core import modlog
from redbot.core.bot import Red
from redbot.core.modlog import register_casetype, register_casetypes



class CrasherBGone(commands.Cog):
    """"I've had it with these motherfucking crashing videos on this motherfucking platform!"""
    default_channel = {
        "enabled" : False
    }
    default_guild = {
        "logtoggle" : False,
        "logmode": "",
        "logchannel": "",
        "action": ""
    }
    def __init__(self, *args, **kwargs):
        super().__init__()
        self.bot = bot
        self.config = Config.get_conf(self, identifier=18082006)
        self.config.register_channel(**self.default_channel)
        async def initialize(self):
            await register_casetypes()
        
        async def red_delete_data_for_user(
            self,
            *,
            requester,
            user_id: int,
        ):
            pass # We don't store user data.
            
    @staticmethod
    async def register_casetypes():
        video_crasher_log = [{
            "name": "video_crash_logger",
            "default_setting": True,
            "image": "\N{MOVIE CAMERA}",
            "case_str": "Posted a Video that can crash Clients."
        }]
        try: await modlog.register_casetypes(**video_crasher_log)
        except: pass

        
    @commands.command(name="crashcheck")
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
    @checks.admin_or_permissions(manage_guild=True)
    async def crcheckadmin(self, ctx):
        """Admin commands for Crash Checker"""

    @crcheckadmin.command(name="togglelog")
    async def _modlogtoggle(self, ctx, Mode: str = None):
        """Toggle whether the modlog is used when a file is deleted. Supported Modes:
        ``` ModLog - Logs to Reds Modlog.None\n
        ChannelLog - Enables logging to a channel set in [p]crcheckadmin logchannel\n
        None - Disables Logging.
        ```
        Omit all options to see the current setting.\n
        NOTE - Options are **NOT** case sensitive."""
        LogGuild = self.config.guild(ctx.guild)
        TogSetting = LogGuild.logtoggle()
        if Mode == None:
            await ctx.reply("Logging to ModLog is currently `{status}`".format(status=TogSetting))
            return
        else:
            if Mode.lower() == "modlog":
                await LogGuild.logmode.set("ModLog")
                await ctx.reply("Cases are now going to Red's ModLog. Or I guess, [botname]'s ModLog.".format(botname=ctx.me.name))
            if Mode.lower() == "channellog":
                await LogGuild.logmode.set("ChannelLog")
                LogChannel = LogGuild.logchannel()
                if LogChannel == "":
                    await ctx.reply("""Incidents will now be going to a defined channel. What that channel is,
                    I don't now, since you **Haven't defined one yet. Please go and do that** - its {p}crcheckadmin logchannel""".format(p=ctx.prefix))
                else:
                    await ctx.reply("""Incidents are now being logged to {channel}""".format(channel=LogChannel))
            if Mode.lower() == "none":
                await LogGuild.logmode.set("None")
                await ctx.reply("Logging Disabled.")
            else:
                await ctx.reply("I think you put an invalid option. Try again, make sure the formatting is correct.")

        