from redbot.core import commands # We going super fucking basic
from typing import Optional




class wikishite(commands.Cog):
    """Here we fuckin go"""
    DEFAULT_URL_SHIT = "https://en.scpslgame.com/index.php?title="
    MY_WIFE_LEFT_ME = "Main_Page"

    @commands.command()
    async def wikishite(self, ctx, *, args = None):
        if args = None:
            URL = DEFAULT_URL_SHIT + MY_WIFE_LEFT_ME
        else:
            args.replace(" ", "_")
            URL = DEFAULT_URL_SHIT + args
        await ctx.send(f"{URL}")
        