import re
import discord
import asyncio
from discord.ext.commands.core import guild_only
from discord.mentions import AllowedMentions
from redbot.core import bot, commands, checks, Config
from redbot.core.bot import Red
from typing import Union
from redbot.core import modlog
from redbot.core.modlog import register_casetype, register_casetypes



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
    def __init__(self, bot: "Red"):
        super().__init__()
        self.bot = bot
        self.config = Config.get_conf(self, identifier=18082006)
        self.config.register_channel(**self.default_channel)
        self.config.register_guild(**self.default_guild)
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
                        case = modlog.create_case(
                            self.bot.user, message.channel.guild, message.created_at, action_type="video_crash_logger", user=message.author,
                            moderator=self.bot.user, reason="`giant.gfycat link that ends in mp4 - I'd recommend checking the link yourself. Content: {link}".format(link=message.content))

