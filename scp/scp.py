from aiohttp import client
import discord
from discord.colour import Color
import pyscp # Installed On Cog install, using https://github.com/NorthWood-Cogs/pyscp
import aiographql
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




    async def CromRequest(self, scp):
        async with aiohttp.ClientSession() as session:
            Client = aiographql.client.GraphQLClient(
                endpoint = "https://api.crom.avn.sh/"
            )
            CromQuery = aiographql.client.GraphQLRequest("""
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
            print(cromURL+CromQuery)
            response: aiographql.client.GraphQLResponse = await Client.query(request=CromQuery)

