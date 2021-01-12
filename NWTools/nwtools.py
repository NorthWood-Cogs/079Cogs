import discord
from discord.utils import get
from redbot.core import commands, Config, checks
from redbot.core.bot import Red
from typing import Optional
import asyncio

### I fucking swear to god that the fact that I need to make this cog a thing because I can't be 100% certain that folks
### won't just fucking massmute folks in the server is the only joke thats bigger than this cogs required existence.
### I WILL NOT be adding proper variable support, and WILL be hardcoding ID's.
### I WILL ONLY allow this cog to function within the SL Discord.
### I WILL tell *anyone* that tells me that this cog isn't up to par, Including Masonic (tho frankly he's probably read this and is just staying away from it)
### To go fuck themselves on a bed of rusty fucking nails - because if I have to fuck my evening over due to trust issues, then fuck you too.
server_id = 535222684880207904
serverhost_id = 492635905811546130
class NWTools(commands.Cog):
    """The long-awaited thing to end the shitshow that is addrole.
    I do not care that theres a swear, this cog is NW only."""
    def __init__(self, bot):
        self.bot = bot
    
    def is_in_server(guild_id):
        async def predicate(ctx):
            return ctx.guild and ctx.guild.id == guild_id
        return commands.check(predicate)

    @commands.command()
    #@is_in_server(server_id)
    #@commands.has_role(773662839289937980)
    @commands.is_owner()
    async def serverhost(self, ctx, user: discord.Member):
        """Toggles the serverhost role on a user."""
        ServerHost = get(ctx.guild.roles, id=serverhost_id)
        if ServerHost in user.roles:
            await user.remove_roles(ServerHost) #Crime, She typed. idk.
            await ctx.send(f"I removed {ServerHost.name} from {user.mention}.")
        else:
            await user.add_roles(ServerHost)
            await ctx.send(f"I have added {ServerHost.name} to {user.mention}")
    
    @commands.command()
    #@is_in_server(server_id)
    #@commands.has_any_role(472408217528434717,472407900443246603,219040433861296128)
    @commands.is_owner()
    async def advert(self, ctx, user: discord.Member):
        advertRole = get(ctx.guild.roles, id=472419831262740510)
        await user.add_roles(advertRole)
        await ctx.send(f"I've added the advert role to {user.mention} and will remove it in 120 seconds.")
        await asyncio.sleep(120)
        await ctx.send(f"I've removed the advert role from {user.mention} as the timer has expired.")
        await user.remove_roles(advertRole) # You taken the hint of how basic we're going?


        
        

