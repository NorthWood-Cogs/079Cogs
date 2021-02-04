import discord
from discord.utils import get
from redbot.core import commands, Config, checks
from redbot.core.bot import Red
from typing import Optional
import asyncio

"""
I fucking swear to god that the fact that I need to make this cog a thing because I can't be 100% certain that folks
won't just fucking massmute folks in the server is the only joke thats bigger than this cogs required existence.
I WILL NOT be adding proper variable support, and WILL be hardcoding ID's.
I WILL ONLY allow this cog to function within the SL Discord.
I WILL tell *anyone* that tells me that this cog isn't up to par, Including Masonic (tho frankly he's probably read this and is just staying away from it)
To go fuck themselves on a bed of rusty fucking nails - because if I have to fuck my evening over due to trust issues, then fuck you too.

See now you can even read it nicely
"""
server_id = 330432627649544202
serverhost_id = 472419831262740510

class NWTools(commands.Cog):
    """The long-awaited thing to end the shitshow that is addrole.
    I do not care that theres a swear, this cog is NW only."""

    def __init__(self, bot):
        self.bot = bot

    # time for the custom checks. since they're mostly similar, i'm keeping them here for now.
    def is_in_server(guild_id):
        async def predicate(ctx):
            return ctx.guild and ctx.guild.id == guild_id

        return commands.check(predicate)  # SL guild only

    def check_senior_ts():
        async def predicate(ctx):
            return ctx.message.author.id == 235520881953210369 or ctx.message.author.id == 124241068727336963

        return commands.check(predicate)  # So only Phoenix and Khaos can add TA roles

    def is_techsupport_channel():
        async def predicate(ctx):
            return ctx.message.channel.id == 472408806211715083

        return commands.check(predicate)  # Only works in #tech-support

    def is_wikifeedback_channel():
        async def predicate(ctx):
            return ctx.message.channel.id == 736009227172053103 and ctx.message.author.id == 224309184294813697

        return commands.check(predicate)  # Only works in #tech-support

    # Repeats over, time for more repeating.

    @commands.command()
    @is_in_server(server_id)
    @commands.has_role(492635905811546130)
    async def serverhost(self, ctx, user: discord.Member):
        """Toggles the serverhost role on a user."""
        ServerHost = get(ctx.guild.roles, id=serverhost_id)
        if ServerHost in user.roles:
            await user.remove_roles(ServerHost)  # Crime, She typed. idk.
            await ctx.send(f"I removed {ServerHost.name} from {user.mention}.")
        else:
            await user.add_roles(ServerHost)
            await ctx.send(f"I have added {ServerHost.name} to {user.mention}")

    @commands.command()
    @is_in_server(server_id)
    @commands.has_any_role(472408217528434717, 472407900443246603, 219040433861296128)
    async def advert(self, ctx, user: discord.Member):
        advertRole = get(ctx.guild.roles, id=472411216677961728)
        await user.add_roles(advertRole)
        await ctx.send(f"I've added the advert role to {user.mention} and will remove it in 120 seconds.")
        await asyncio.sleep(120)
        await ctx.send(f"I've removed the advert role from {user.mention} as the timer has expired.")
        await user.remove_roles(advertRole)  # You taken the hint of how basic we're going?

    @commands.group()
    @commands.has_role(472408645305499659)
    @is_in_server(server_id)
    async def ts(self, ctx):
        """Tech support Commands"""

    @ts.command()
    @check_senior_ts()
    async def tatoggle(self, ctx, user: discord.Member):
        """Toggles the TA role on a user."""
        techAssistRole = get(ctx.guild.roles, id=716363340334759947)
        if techAssistRole in user.roles:
            await user.remove_roles(techAssistRole)  # Crime, She typed. idk.
            await ctx.send(f"I removed {techAssistRole.name} from {user.mention}.")
        else:
            await user.add_roles(techAssistRole)
            await ctx.send(f"I have added {techAssistRole.name} to {user.mention}")

    @ts.command()
    @is_techsupport_channel()
    async def togglemute(self, ctx, user: discord.Member):
        """Mute or unmute user in #tech-support. Finally!"""
        permies = ctx.channel.overwrites_for(user)
        if permies.send_messages is True or permies.send_messages is None:
            permies.send_messages = False
            await ctx.channel.set_permissions(user, overwrite=permies, reason="Muted By TS in #tech-support")
            await ctx.send(f"{user.name} has been muted in this channel.")
        else:
            permies.send_messages = None
            await ctx.channel.set_permissions(user, overwrite=permies, reason="unmuted By TS in #tech-support")
            await ctx.send(f"{user.name} has been unmuted in this channel.")

    @commands.command(name="steb")
    @is_wikifeedback_channel()
    async def _terransmagicalmute(self, ctx, user: discord.Member):
        """I hate the name of this command. Mute or Unmute folks in #wiki-feedback."""
        permies = ctx.channel.overwrites_for(user)
        if permies.send_messages is True or permies.send_messages is None:
            permies.send_messages = False
            await ctx.channel.set_permissions(user, overwrite=permies, reason="Muted By TerranHawk in #wiki-feedback")
            await ctx.send(f"{user.name} has been muted in this channel.")
        else:
            permies.send_messages = None
            await ctx.channel.set_permissions(user, overwrite=permies, reason="unmuted By TerranHawk in #wiki-feedback")
            await ctx.send(f"{user.name} has been unmuted in this channel.")

    @commands.group()  # This is my first edit. Please be kind :(
    @commands.has_role(485570011084095488)
    @is_in_server(server_id)
    async def pr(self, ctx):
        """Patreon representative Commands"""
        async with ctx.typing():
            if ctx.invoked_subcommand is None:
                await ctx.send('Please use ``!pr tsr <USER>`` to toggle user\'s role')

    @pr.command()
    async def tsr(self, ctx, user: discord.Member):
        """Toggles the Patreon supporter role on a user."""
        ptrn_sup_role = get(ctx.guild.roles, id=472410137118900244)
        if not user:
            await ctx.send("You have to define a user using ``!pr tsr <USER>''")
        else:
            if ptrn_sup_role in user.roles:
                await user.remove_roles(ptrn_sup_role)  # Crime, She typed. idk.
                await ctx.send(f"I removed {ptrn_sup_role.name} from {user.mention}.")
            else:
                await user.add_roles(ptrn_sup_role)
                await ctx.send(f"I have added {ptrn_sup_role.name} to {user.mention}")
