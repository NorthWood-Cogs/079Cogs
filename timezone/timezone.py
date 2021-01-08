import asyncio
import discord
import datetime
import pytz
from redbot.core import commands, Config, checks
from redbot.core.utils.predicates import MessagePredicate
from typing import Optional, Union
from .extra import *

class Timezone(commands.Cog):
    """Commands related to setting up TimeZone roles"""
    default_user = {"timezone": None}

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, 8237492837453329, force_registration=True)
        self.config.register_user(**self.default_user)

    @commands.command(name="timezone", aliases=["tz"])
    async def assignTimeZone(self, ctx, timezone : TimeZoneConverter):
        """Assign Timezone Role. Timezone DB https://en.wikipedia.org/wiki/List_of_tz_database_time_zones"""
        await self.setMemberTimezone(ctx, ctx.author, timezone)

    @commands.group(name="timezoneadmin", aliases=["tza"])
    @checks.guildowner_or_permissions(manage_roles=True, manage_guild=True)
    @commands.guild_only()
    async def timezoneset(self, ctx):
        """Timezone Commands"""
        pass

    @timezoneset.command(name="setup")
    async def createRoles(self, ctx):
        """Will create roles needed to cover all timezones (25 Roles)"""
        if not ctx.guild.me.guild_permissions.manage_roles:
            return await ctx.send("I do not have `Manage Roles` permission.")
        count = 0
        async with ctx.typing():
            for x in range(-12, 13):
                hour = (str(x).zfill(3) if x < 0 else str(x).zfill(2))
                if hour.isdigit():
                    hour = f"+{hour}"
                await ctx.guild.create_role(name=f"UTC{hour}:00", mentionable=False, reason="Setup TZ Roles")
                count += 1
        await ctx.send(f"Created {count} roles.")

    @timezoneset.command(name="clearroles", aliases=["cleanup"])
    async def cleanUp(self, ctx):
        """Will remove all roles beginning with "UTC\""""
        if not ctx.guild.me.guild_permissions.manage_roles:
            return await ctx.send("I do not have `Manage Roles` permission.")
        count = 0
        async with ctx.typing():
            for role in ctx.guild.roles:
                if role.name.startswith("UTC"):
                    await role.delete()
                    count += 1
        await ctx.send(f"Deleted {count} roles.")

    async def setMemberTimezone(self, ctx, member : discord.User, timezone : datetime.timezone):
        tz = await self.config.user(member).timezone()
        if tz is not None:
            role = discord.utils.find(lambda r: r.name == tz, ctx.guild.roles)
            if role is not None:
                await member.remove_roles(role)
            else:
                print("Failed to remove Timezone role")
        if str(timezone) == "UTC":
            timezone = "UTC+00:00"
        role = discord.utils.find(lambda r: r.name == str(timezone), ctx.guild.roles)
        if role is not None: 
            await member.add_roles(role)
            await ctx.send(f"{timezone} Role added")
            await self.config.user(member).timezone.set(str(timezone))
        else:
            await ctx.send(f"*{timezone} Role not found.*")