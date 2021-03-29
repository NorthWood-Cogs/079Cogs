import collections
import re
import datetime
import discord
import asyncio

from redbot.core import commands, Config, utils
from dateutil.parser import parse
from typing import Literal, Optional, Union
from redbot.core.utils.predicates import MessagePredicate


class Date(commands.Converter):
    @staticmethod
    async def convert(_, arg):
        result = None
        try:
            result = parse(arg)
        except ValueError:
            result = None
        if result is None:
            raise commands.BadArgument('Unable to parse Date "{}" '.format(arg))
        return result

    @staticmethod
    async def from_string(arg):
        try:
            result = parse(arg)
        except ValueError:
            result = None
        return result


class Time(commands.Converter):
    time_amnt_regex = re.compile("([1-9][0-9]*)([a-z]+)", re.IGNORECASE)
    time_quantities = collections.OrderedDict(
        [
            ("seconds", 1),
            ("minutes", 60),
            ("hours", 3600),
            ("days", 86400),
            ("weeks", 604800),
            ("months", 2.628e6),
            ("years", 3.154e7),
        ]
    )  # (amount in seconds, max amount)

    async def convert(self, ctx, arg):
        seconds = self.get_seconds(arg)
        time_now = datetime.datetime.utcnow()
        days, secs = divmod(seconds, 3600 * 24)
        end_time = time_now + datetime.timedelta(days=days, seconds=secs)
        result = end_time
        if result is None:
            raise commands.BadArgument('Unable to parse Date "{}" '.format(arg))
        return result

    @classmethod
    async def from_string(cls, arg):
        seconds = cls.get_seconds(cls, arg)
        time_now = datetime.datetime.utcnow()
        if seconds is not None:
            days, secs = divmod(seconds, 3600 * 24)
            end_time = time_now + datetime.timedelta(days=days, seconds=secs)
            return end_time
        else:
            return None

    def get_seconds(self, time):
        """Returns the amount of converted time or None if invalid"""
        seconds = 0
        for time_match in self.time_amnt_regex.finditer(time):
            time_amnt = int(time_match.group(1))
            time_abbrev = time_match.group(2)
            time_quantity = discord.utils.find(
                lambda t: t[0].startswith(time_abbrev), self.time_quantities.items()
            )
            if time_quantity is not None:
                seconds += time_amnt * time_quantity[1]
        return None if seconds == 0 else seconds


class LOACog(commands.Cog):
    """Commands for creating Leave of Abscences"""

    default_guild = {
        "loas": [],
        "scheduledLoas": [],
        "loaChannel": None,
        "loggingChannel": None,
        "managerRoles": [],
        "staffRoles": [],
        "loaRoleID": None,
    }

    def __init__(self, bot, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bot = bot
        self.config = Config.get_conf(self, 8237492837454039, force_registration=True)
        self.config.register_guild(**self.default_guild)
        self.futures = []
        self.time_format = (
            "%b %d, %Y @ %I:%M %p UTC"
        )  # https://docs.python.org/2/library/datetime.html#strftime-strptime-behavior
        asyncio.ensure_future(self.restart_loas())

    async def red_delete_data_for_user(
            self,
            *,
            requester: Literal["discord_deleted_user", "owner", "user", "user_strict"],
            user_id: int,
    ):

        pass  # LOAs are manually detonatable, So I'll hook it together at some point

    def is_admin_or_higher_or_botdev(self, ctx):
        utils.mod.is_admin_or_superior(self.bot, ctx.author) or ctx.author.is_owner()

    async def is_manager(self, ctx):
        managerRoles = await self.config.guild(ctx.guild).managerRoles()
        member = ctx.author
        if member.guild_permissions.administrator or member.guild_permissions.manage_roles:
            return True
        if await utils.mod.is_admin_or_superior(self.bot, member):
            return True
        for role in member.roles:
            if role.id in managerRoles:
                return True
        return False

    @commands.group()
    @commands.guild_only()
    async def loa(self, ctx):
        if ctx.invoked_subcommand is None:
            pass

    @loa.command(name="submit", aliases=["create"])
    async def submit_loa(self, ctx, user: Optional[discord.Member] = None):
        """Submit a Leave of Absence for your staff position"""
        guild = ctx.guild
        if user is None or user == ctx.author:
            user = ctx.author
        elif user is not None and not await self.is_manager(ctx):
            return await ctx.maybe_send_embed("You are not allowed to submit LOAs for others.")
        scheduled_loas = await self.config.guild(guild).scheduledLoas()
        loas_of_author = [loa for loa in scheduled_loas if loa["authorID"] == user.id]
        if loas_of_author:
            loa = loas_of_author[0]
            return await self.previewloa("scheduled", ctx, user, loa)
        guild_loas = await self.config.guild(guild).loas()
        loas_of_guild = [loa for loa in guild_loas if loa["authorID"] == user.id]
        if loas_of_guild:
            loa = loas_of_guild[0]
            return await self.previewloa("started", ctx, user, loa)

        startdate, enddate, reason = None, None, None
        try:
            startdate, enddate, reason = await self.loa_time_input(ctx)
        except TypeError as e:
            print(e)
        if reason is None:
            return await ctx.maybe_send_embed("You must provide a reason for your LOA.")
        if startdate is None:
            start_time = datetime.datetime.utcnow()
            delay = 0
        else:
            start_time = startdate
            delay = int((start_time - datetime.datetime.utcnow()).total_seconds())
        if enddate is None:
            return await ctx.maybe_send_embed("You must provide a valid End Date for your LOA.")
        end_time = enddate
        loa = {
            "messageID": None,
            "ctxChannelID": ctx.message.channel.id,
            "authorID": user.id,
            "start_time": start_time.timestamp(),
            "end_time": end_time.timestamp(),
            "reason": reason,
        }
        if start_time > datetime.datetime.utcnow():
            em = discord.Embed(
                title="Staff Leave of Abscence",
                description="Your LOA has been scheduled.",
                color=0xFF8800
            )
            em.set_thumbnail(url=user.avatar_url)
            em.add_field(name="Staff Name", value=user.mention)
            em.add_field(name="Reason", value=reason)
            em.add_field(name="Starts On", value=start_time.strftime(self.time_format))
            em.add_field(name="Ends On", value=end_time.strftime(self.time_format))
            await ctx.send(embed=em)

            await self.logloa(guild, "scheduled", user, loa)
            async with self.config.guild(guild).scheduledLoas() as sLoas:
                sLoas.append(loa)
        self.futures.append(asyncio.ensure_future(self.startloa(ctx, user, delay, loa)))

    async def previewloa(self, state, ctx, user, loa):
        start_time = datetime.datetime.fromtimestamp(loa["start_time"]).strftime(self.time_format)
        end_time = datetime.datetime.fromtimestamp(loa["end_time"]).strftime(self.time_format)
        reason = loa["reason"]
        color = None
        if state.lower() == "started":
            color = 0x3DF270
        elif state.lower() == "scheduled":
            color = 0xFF8800
        title = "Staff Leave of Abscence"
        em = discord.Embed(title=title, color=color)
        em.set_author(name=title)
        em.set_thumbnail(url=user.avatar_url)
        em.add_field(name="Staff Name", value=user.mention)
        em.add_field(name="Reason", value=reason)
        em.add_field(name="Starts On", value=start_time)
        em.add_field(name="Ends On", value=end_time, inline=False)
        if state.lower() == "started":
            await ctx.send(
                content=f"{user.name} already has an active LOA. Use `!loa cancel` to cancel the active LOA.",
                embed=em,
            )
        elif state.lower() == "scheduled":
            await ctx.send(
                content=f"{user.name} already has a scheduled LOA. Use `!loa cancel` to cancel the scheduled LOA.",
                embed=em,
            )

    @loa.command(name="cancel", aliases=["remove", "delete"])
    async def usercancelloa(self, ctx, user: discord.Member = None):
        """Cancel an active or scheduled LOA"""
        guild = ctx.guild

        if user is None or user == ctx.author:
            user = ctx.author
        elif user is not None and not await self.is_manager(ctx):
            return await ctx.maybe_send_embed("You are not allowed to cancel LOAs for others.")
        guild_loas = await self.config.guild(guild).loas()
        guild_user_loas = [loa for loa in guild_loas if loa["authorID"] == user.id]
        if guild_user_loas:
            for loa in guild_user_loas:
                await self.cancelloa(guild, loa, ctx.author)
        scheduled_loas = await self.config.guild(guild).scheduledLoas()
        guild_scheduled_loas = [loa for loa in scheduled_loas if loa["authorID"] == user.id]
        if guild_scheduled_loas:
            for loa in guild_scheduled_loas:
                await self.cancelloa(guild, loa, ctx.author)
        role = ctx.guild.get_role(await self.config.guild(guild).loaRoleID())
        if role is not None:
            try:
                await user.remove_roles(role, reason="Ended Leave of Abscence")
            except discord.Forbidden:
                pass
        if not guild_user_loas and not guild_scheduled_loas:
            await ctx.maybe_send_embed(
                f"`{user.display_name}` does not have an active or scheduled LOA."
            )

    @staticmethod
    async def loa_time_input(ctx: commands.Context):
        """Handles getting Start and End Dates/Times for LOAs"""
        await ctx.maybe_send_embed(
            "When will your LOA begin? Enter as *`month/day`* or *`3d`*." + "\n"
                                                                            "Enter *`now`* if it will begin right now." + "\n"
                                                                                                                          "Enter *`cancel`* to cancel submission."
        )
        try:
            msg = await ctx.bot.wait_for(
                "message", check=MessagePredicate.same_context(ctx), timeout=60
            )
        except asyncio.TimeoutError:
            return await ctx.maybe_send_embed("LOA Submission Cancelled.")
        if msg.content.lower().strip() in ["exit", "cancel", "stop", "no"]:
            return await ctx.maybe_send_embed("LOA Submission Cancelled.")
        startdate = await Time.from_string(msg.content)
        if startdate is None:
            startdate = await Date.from_string(msg.content)
        await ctx.maybe_send_embed(
            "When will your LOA end? Enter as *`month/day`* or *`3d`*." + "\n"
                                                                          "Enter *`cancel`* to cancel submission."
        )
        try:
            msg = await ctx.bot.wait_for(
                "message", check=MessagePredicate.same_context(ctx), timeout=60
            )
        except asyncio.TimeoutError:
            return await ctx.maybe_send_embed("LOA Submission Cancelled.")
        if msg.content.lower().strip() in ["exit", "cancel", "stop", "no"]:
            return await ctx.maybe_send_embed("LOA Submission Cancelled.")
        enddate = await Time.from_string(msg.content)
        if enddate is None:
            enddate = await Date.from_string(msg.content)
        if enddate is None:
            return await ctx.maybe_send_embed("Unable to parse End Date.")
        await ctx.maybe_send_embed(
            "Enter your reason for your LOA." + "\n" "Enter *`cancel`* to cancel submission."
        )
        try:
            msg = await ctx.bot.wait_for(
                "message", check=MessagePredicate.same_context(ctx), timeout=45
            )
        except asyncio.TimeoutError:
            return await ctx.maybe_send_embed("LOA Submission Cancelled.")
        if msg.content.lower().strip() in ["exit", "cancel", "stop", "no"]:
            return await ctx.maybe_send_embed("LOA Submission Cancelled.")
        reason = msg.content
        return startdate, enddate, reason

    async def startloa(self, ctx, user, delay, loa):
        """Begins and Activates LOA within LOA Channel"""
        await asyncio.sleep(delay)
        guild = ctx.guild
        start_time = datetime.datetime.fromtimestamp(loa["start_time"]).strftime(self.time_format)
        end_time = datetime.datetime.fromtimestamp(loa["end_time"]).strftime(self.time_format)
        reason = loa["reason"]

        em = discord.Embed(
            title="Staff Leave of Abscence",
            color=0x3DF270)
        em.set_thumbnail(url=user.avatar_url)
        em.add_field(name="Staff Name", value=user.mention)
        if reason is not None:
            em.add_field(name="Reason", value=reason)
        em.add_field(name="Starts On", value=start_time)
        em.add_field(name="Ends On", value=end_time, inline=False)

        loaChannel = self.bot.get_channel(await self.config.guild(guild).loaChannel())
        try:
            message = await loaChannel.send(embed=em)
        except discord.Forbidden:
            await ctx.send("I do not have permissions to send a message in " + loaChannel.mention)
        except AttributeError:
            await ctx.send("LOA Channel is not set.")
        else:
            await ctx.send(f"Leave Of Abscence created in {loaChannel.mention}.")
            async with self.config.guild(guild).scheduledLoas() as sLoas:
                if loa in sLoas:
                    sLoas.remove(loa)
            loa["messageID"] = message.id
            seconds = (
                    datetime.datetime.fromtimestamp(loa["end_time"]) - datetime.datetime.utcnow()
            ).total_seconds()
            channel = ctx
            async with self.config.guild(guild).loas() as loas:
                loas.append(loa)
            self.futures.append(
                asyncio.ensure_future(self.remind_loa_ended(user, channel, message, seconds, loa))
            )
            role = ctx.guild.get_role(await self.config.guild(guild).loaRoleID())
            if role is not None:
                try:
                    await user.add_roles(role, reason="Started Leave of Abscence")
                except discord.Forbidden:
                    pass
            await self.logloa(guild, "started", user, loa)

    async def cancelloa(self, guild, loa, issuer: discord.Member = None):
        loaChannel = await self.config.guild(guild).loaChannel()
        if not loaChannel:
            raise discord.ext.commands.BadArgument
        loaChannel = self.bot.get_channel(loaChannel)
        user = self.bot.get_user(loa["authorID"])
        start_time = datetime.datetime.fromtimestamp(loa["start_time"]).strftime(self.time_format)
        end_time = datetime.datetime.fromtimestamp(loa["end_time"]).strftime(self.time_format)

        em = discord.Embed(
            title="Staff Leave of Abscence",
            description="Your LOA has been cancelled.",
            color=0x820000
        )
        if user is None:  # User not found
            user2 = self.bot.get_user_info(loa["authorID"])
            if user2 is not None:
                em.add_field(name="Staff Name", value=user2.name, inline=False)
        em.add_field(name="Start Time", value=start_time)
        em.add_field(name="End Time", value=end_time, inline=False)
        em.add_field(name="Reason", value=loa["reason"], inline=False)

        channel = self.bot.get_channel(loa["ctxChannelID"])
        async with self.config.guild(guild).scheduledLoas() as sLoas:
            if loa in sLoas:
                sLoas.remove(loa)
        async with self.config.guild(guild).loas() as loas:
            if loa in loas:
                try:
                    loas.remove(loa)
                except ValueError:
                    pass
        message = None
        if loa["messageID"] is not None:
            try:
                message = await loaChannel.fetch_message(loa["messageID"])
            except discord.NotFound:
                pass
        try:
            await channel.send(content=user.mention, embed=em)
        except AttributeError:
            await channel.send(embed=em)
        except discord.Forbidden:
            pass
        if message is not None:
            try:
                await message.delete()
            except discord.Forbidden:
                pass
        if issuer is not None:
            await self.logloa(guild, "cancelled", user, loa, issuer)
        else:
            await self.logloa(guild, "cancelled", user, loa)
        await self.cleanup_tasks()

    async def logloa(self, guild, state, user, loa, issuer: discord.Member = None):
        """"Logs LOA and it's started/ended status to Config's LOA Logging Channel."""
        loggingChannel = await self.config.guild(guild).loggingChannel()
        logChannel = self.bot.get_channel(loggingChannel)
        start_time = datetime.datetime.fromtimestamp(loa["start_time"]).strftime(self.time_format)
        end_time = datetime.datetime.fromtimestamp(loa["end_time"]).strftime(self.time_format)
        reason = loa["reason"]
        _color = None
        if state.lower() == "started":
            _color = 0x3DF270
        elif state.lower() == "scheduled":
            _color = 0xFF8800
        elif state.lower() == "cancelled":
            _color = 0x820000
        else:
            _color = discord.Color.red()

        em = discord.Embed(
            title="Staff Leave of Abscence" + state.capitalize(),
            color=_color)
        if state.lower() == "cancelled" and issuer is not None:
            em.set_footer(text=f"Issued by {issuer.display_name}", icon_url=issuer.avatar_url)
        em.set_thumbnail(url=user.avatar_url)
        em.add_field(name="Staff Name", value=user.mention)
        if reason is not None:
            em.add_field(name="Reason", value=reason)
        em.add_field(name="Start Date", value=start_time)
        em.add_field(name="End Date", value=end_time)

        try:
            await logChannel.send(embed=em)
        except discord.Forbidden:
            pass

    async def remind_loa_ended(self, user, channel, message, seconds, loa):
        """Deletes the LOA and reminds the author their LOA has ended."""
        guild = channel.guild
        await asyncio.sleep(seconds)
        start_time = datetime.datetime.fromtimestamp(loa["start_time"]).strftime(self.time_format)
        end_time = datetime.datetime.fromtimestamp(loa["end_time"]).strftime(self.time_format)
        title = "Staff Leave of Abscence"
        em = discord.Embed(
            title=title,
            description=f"Your LOA has ended.",
            color=discord.Color.red()
        )
        em.add_field(name="Start Time", value=start_time)
        em.add_field(name="End Time", value=end_time, inline=False)
        em.add_field(name="Reason", value=loa["reason"], inline=False)

        async with self.config.guild(guild).loas() as loas:
            if loa in loas:
                try:
                    loas.remove(loa)
                except ValueError:
                    pass
                await channel.send(content=user.mention, embed=em)
        if message is not None:
            try:
                await message.delete()
            except discord.Forbidden:
                pass
        role = channel.guild.get_role(await self.config.guild(guild).loaRoleID())
        if role is not None:
            try:
                await user.remove_roles(role, reason="Ended Leave of Abscence")
            except discord.Forbidden:
                pass
        await self.logloa(guild, "ended", user, loa)
        await self.cleanup_tasks()

    async def restart_loas(self):
        await self.bot.wait_until_ready()
        # async for guild in self.bot.fetch_guilds(): #Uncomment once we update to
        for guild in self.bot.guilds:
            for loa in await self.config.guild(guild).loas():
                time_diff = (
                        datetime.datetime.fromtimestamp(loa["end_time"]) - datetime.datetime.utcnow()
                )
                seconds = max(0, int(time_diff.total_seconds()))
                user = self.bot.get_user(loa["authorID"])
                channel = self.bot.get_channel(loa["ctxChannelID"])
                loaChannel = self.bot.get_channel(await self.config.guild(guild).loaChannel())
                try:
                    message = await loaChannel.fetch_message(loa["messageID"])
                except discord.NotFound:  # If LOA not found in LoaChannel, assume it was deleted by management and
                    # end LOA.
                    await self.cancelloa(guild, loa)
                    continue
                self.futures.append(
                    asyncio.ensure_future(
                        self.remind_loa_ended(user, channel, message, seconds, loa)
                    )
                )
            for loa in await self.config.guild(guild).scheduledLoas():
                user = self.bot.get_user(loa["authorID"])
                ctx = self.bot.get_channel(loa["ctxChannelID"])
                start_time = datetime.datetime.fromtimestamp(loa["start_time"])
                delay = int((start_time - datetime.datetime.utcnow()).total_seconds())
                self.futures.append(asyncio.ensure_future(self.startloa(ctx, user, delay, loa)))

    async def cleanup_tasks(self):
        for future in self.futures:
            if future.done():
                future.cancel()

    @loa.command(aliases=["setchannel"])
    async def setloachannel(self, ctx, channel: discord.TextChannel):
        """Set the LOA's Channel in Config"""
        guild = ctx.guild
        if not await self.is_manager(ctx):
            try:
                await ctx.maybe_send_embed("You do not have permission to use this command.")
            except discord.Forbidden:
                pass
            return
        prevloaChannel = await self.config.guild(guild).loaChannel()
        if prevloaChannel == channel.id:
            return await ctx.maybe_send_embed(f"LOA Channel is already set to {channel.mention}.")

        prevloaChannel = self.bot.get_channel(prevloaChannel)
        await self.config.guild(guild).loaChannel.set(channel.id)
        loaChannel = await self.config.guild(guild).loaChannel()
        loaChannel = self.bot.get_channel(loaChannel)
        if loaChannel is not None:
            if prevloaChannel is not None:
                await ctx.maybe_send_embed(
                    f"LOA Channel updated from {prevloaChannel.mention} to {loaChannel.mention}."
                )
            else:
                await ctx.maybe_send_embed(f"LOA Channel updated to {loaChannel.mention}.")
        else:
            await ctx.maybe_send_embed("Channel not found.")

    @loa.command(aliases=["setlogging"])
    async def setloggingchannel(self, ctx, channel: discord.TextChannel):
        """Set the LOA's Logging Channel in Config"""
        guild = ctx.guild
        if not await self.is_manager(ctx):
            try:
                await ctx.maybe_send_embed("You do not have permission to use this command.")
            except discord.Forbidden:
                pass
            return
        prevloggingChannel = await self.config.guild(guild).loggingChannel()
        if prevloggingChannel == channel.id:
            await ctx.send(f"LOA Logging Channel is already set to {channel.mention}.")
            return

        prevloggingChannel = self.bot.get_channel(prevloggingChannel)
        await self.config.guild(guild).loggingChannel.set(channel.id)
        loggingChannel = await self.config.guild(guild).loggingChannel()
        loggingChannel = self.bot.get_channel(loggingChannel)
        if prevloggingChannel is None:
            await ctx.maybe_send_embed(f"LOA Logging Channel updated to {loggingChannel.mention}.")
        else:
            await ctx.maybe_send_embed(
                f"LOA Logging Channel updated from {prevloggingChannel.mention} to {loggingChannel.mention}."
            )

    @loa.command(name="setrole", aliases=["role"])
    async def setrole(self, ctx, role: Union[discord.Role, str]):
        """Set the Role to be given to those who are on active LOA"""
        guild = ctx.guild
        if not await self.is_manager(ctx):
            try:
                await ctx.maybe_send_embed("You do not have permission to use this command.")
            except discord.Forbidden:
                pass
            return
        if type(role) == str:
            if role.lower().strip() == "none":
                await self.config.guild(guild).loaRoleID.set(None)
                return await ctx.maybe_send_embed("LOA Role removed.")
            else:
                return await ctx.maybe_send_embed(f'Role "{role}" not found.')
        prevRole = await self.config.guild(guild).loaRoleID()
        if prevRole == role.id:
            return await ctx.maybe_send_embed(f"LOA Role is already set to `{role}`")
        prevRole = ctx.guild.get_role(prevRole)
        await self.config.guild(guild).loaRoleID.set(role.id)
        if prevRole is None:
            await ctx.maybe_send_embed(f"LOA Role updated to `{role}`")
        else:
            await ctx.maybe_send_embed(f"LOA Role updated from `{prevRole}` to `{role}`")

    @loa.command(name="setmanagerroles", aliases=["managers"])
    async def set_manager_roles(self, ctx, *roles: discord.Role):
        """Set which roles will consider a user a manager and give access to LOA Manager commands"""
        if not await self.is_manager(ctx):
            try:
                await ctx.maybe_send_embed("You do not have permission to use this command.")
            except discord.Forbidden:
                pass
            return
        guild = ctx.guild
        if roles:
            msg = f"```diff\nMade the following changes to {ctx.guild.name}'s Manager Roles list:\n\n"
            async with self.config.guild(guild).managerRoles() as managerRoles:
                for role in roles:
                    if role.id in managerRoles:
                        managerRoles.remove(role.id)
                        msg += f"- Removed Manager Role : {role.name} ({role.id})\n"
                    else:
                        managerRoles.append(role.id)
                        msg += f"+ Added Manager Role : {role.name} ({role.id})"
            msg += "```"
        else:
            msg = f"```css\n{ctx.guild.name}'s Manager Roles List\n"
            managerRoles = await self.config.guild(guild).managerRoles()
            if managerRoles:
                for roleID in managerRoles:
                    role = guild.get_role(roleID)
                    if role:
                        msg += f"{role.name} ({role.id})\n"
            else:
                msg += "None\n"
            msg += "```"
        await ctx.send(msg)

    @loa.command(hidden=True)
    async def listloas(self, ctx):
        """List current LOAs loaded from config. For debugging purposes."""
        if not self.is_admin_or_higher_or_botdev(ctx):
            try:
                await ctx.send(
                    "You must be a part of Northwood Management or NW Bot Engineer to use this command."
                )
            except discord.Forbidden:
                pass
            return
        done = [future.done() for future in self.futures]
        sLoas = await self.config.guild(ctx.guild).scheduledLoas()
        async with self.config.guild(ctx.guild).loas() as loas:
            await ctx.send(
                f"`{len(loas)}`   LOAs in config."
                + "\n"
                + f"`{len(sLoas)}`   Scheduled LOAs in config."
                + "\n"
                + f"`{len(done)}/{len(self.futures)}`   Futures in config."
            )

    async def on_message_delete(self, message):
        guild = message.guild
        if not guild:
            return
        loaChannel = await self.config.guild(guild).loaChannel()
        loaChannel = self.bot.get_channel(loaChannel)
        if loaChannel is None:
            pass
        else:
            if message.channel == loaChannel:
                loas = await self.config.guild(guild).loas()
                loas = [loa for loa in loas if loa["messageID"] == message.id]
                if len(loas) > 0:  # Confirm that message deleted is a LOA
                    if message.guild.me.guild_permissions.view_audit_log:
                        async for entry in message.guild.audit_logs(
                                action=discord.AuditLogAction.message_delete, limit=1
                        ):
                            if entry.extra.channel == loaChannel:
                                issuer = entry.user
                                await self.cancelloa(guild, loas[0], issuer)
                    else:  # Bot does not have Audit Log Perms
                        await self.cancelloa(guild, loas[0])
