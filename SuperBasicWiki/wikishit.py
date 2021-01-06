import discord
from redbot.core import commands # We going super fucking basic
from redbot.core.bot import Red
from typing import Optional
DEFAULT_URL_SHIT = "https://en.scpslgame.com/index.php?title="
MY_WIFE_LEFT_ME = "Main_Page"


class wikishite(commands.Cog):
    """Here we fuckin go"""
    def __init__(self, bot: Red):
        self.bot = bot

    @commands.command()
    async def wiki(self, ctx, *, args = None):
        if args == None:
            URL = DEFAULT_URL_SHIT + MY_WIFE_LEFT_ME
        else:
            NewArgs = args.replace(" ", "_")
            URL = DEFAULT_URL_SHIT + NewArgs
        await ctx.send(f"{URL}", allowed_mentions=discord.AllowedMentions(everyone=False, roles=False, users=False))
        # Finally, a useful thing
