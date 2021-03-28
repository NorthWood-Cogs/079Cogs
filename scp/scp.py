from aiohttp import client
import discord
from discord.colour import Color
import pyscp # Installed On Cog install, using https://github.com/NorthWood-Cogs/pyscp
from aiographql import client
import aiohttp
from redbot.core import commands, Config, data_manager
import regex


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
        await self.CromRequest(ctx, scp)
        await ctx.send(self.bot.name)




    async def CromRequest(self, ctx, scp):
        async with aiohttp.ClientSession() as session:
            Client = client.GraphQLClient(
                endpoint = "https://api.crom.avn.sh/"
            )
            CromQuery = client.GraphQLRequest("""
            {{
            searchPages(query: "{targetScp}")
                {{
                    url
                    wikidotInfo {{
                        title
                        rating
                        thumbnailUrl
                    }}
                    alternateTitles {{
                        type
                        title
                    }}
                    attributions {{
                        type
                        user {{
                            name
                        }}
                    }}
                }}
            }}""".format(targetScp=scp))
            print(str(CromQuery))
            response: client.GraphQLResponse = await Client.query(request=CromQuery)
            print(response)
            title = regex.search("url", str(response)).group()
            print(title)
            await session.close()


