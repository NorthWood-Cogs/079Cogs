import discord
from discord import embeds
from discord.embeds import Embed
import pyscp # No longer used maybe i haven't made my mind up yet
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
        emb = await self.CromRequest(ctx, scp)
        await ctx.send(embed=emb)



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
            }}""".format(targetScp=scp.title))
            response: client.GraphQLResponse = await Client.query(request=CromQuery)
            respJson = response.json
            emTitle = (f"{respJson['data']['searchPages'][0]['wikidotInfo']['title']}")
            emName = (f"{respJson['data']['searchPages'][0]['alternateTitles'][0]['title']}")
            emImage = (f"{respJson['data']['searchPages'][0]['wikidotInfo']['thumbnailUrl']}")
            emURL = (f"{respJson['data']['searchPages'][0]['url']}")
        em = discord.Embed(
           title=(f"{emTitle} - {emName}"),
            url=emURL,
        )
        if emImage != "None":
            em.set_image(url=emImage)

        await session.close()
        return em


