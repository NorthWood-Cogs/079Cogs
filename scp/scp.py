from aiohttp import client
import discord
from discord.colour import Color
import pyscp # Installed On Cog install, using https://github.com/NorthWood-Cogs/pyscp
from aiographql import client
import aiohttp
from redbot.core import commands, Config, data_manager


cromURL = "https://api.crom.avn.sh/"

class SCP(commands.Cog):
    """ SCP Cog that utilises Crom - https://crom.avn.sh/"""
    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier="3957890832758296589023290568043")
        self.config.register_global(
                isthisjustawayofsavingmytime=True,
                configLocation=str(data_manager.cog_data_path(self) / "scp.db")
        )    

    @commands.command(name="scp")
    async def _scp(self, ctx, *, scp: str):
        await self.CromRequest(scp)




    def CromRequest(self, scp):
        response = yield from aiohttp.request("GET", """'https://api.crom.avn.sh/' -H 'Accept-Encoding: gzip, deflate, br' -H 'Content-Type: application/json' -H 'Accept: application/json' -H 'Connection: keep-alive' -H 'DNT: 1' -H 'Origin: https://api.crom.avn.sh' --data-binary '{"query":"{\n  searchPages(query: \"{targetScp}\") {\n    url\n    wikidotInfo {\n      title\n      rating\n      thumbnailUrl\n    }\n    alternateTitles {\n      type\n      title\n    }\n    attributions {\n      type\n      user {\n        name\n      }\n    }\n  }\n}\n"}' --compressed}""".format(targetScp=scp))
        print(repr(response))

