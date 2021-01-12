import discord
from redbot.core import commands, Config, checks
from redbot.core.bot import Red
from typing import Optional

### I fucking swear to god that the fact that I need to make this cog a thing because I can't be 100% certain that folks
### won't just fucking massmute folks in the server is the only joke thats bigger than this cogs required existence.
### I WILL NOT be adding proper variable support, and WILL be hardcoding ID's.
### I WILL ONLY allow this cog to function within the SL Discord.
### I WILL tell *anyone* that tells me that this cog isn't up to par, Including Masonic (tho frankly he's probably read this and is just staying away from it)
### To go fuck themselves on a bed of rusty fucking nails - because if I have to fuck my evening over due to trust issues, then fuck you too.

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
    @is_in_server(535222684880207904)
    @commands.has_role(773662839289937980)
    @commands.has_role(588355805061971990)
    async def wellhellothere(self, ctx):
        await ctx.send("General Kenobi")

