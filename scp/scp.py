import discord
import random
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
                #configLocation=str(data_manager.cog_data_path(self) / "scp.db")
        )

    @commands.command(name="scp")
    async def _scp(self, ctx, *, scp: str):
        """Attempts to search for an SCP. Denote them with `-ex` or `-j` to go for explained/joke scp's (and others!)
            Searching by ID is almost always ideal, though names will work in most cases - Pascal Case is ideal.""" 
        if len(scp) <= 2 and scp.isdecimal():
            scpID = scp.replace(" ", "")
            scpToSearch = (f"{scpID.zfill(3)}")
        else:
            scpToSearch = scp
        theBot = ctx.guild.me
        if scp == "0" or scp == "00" or scp == "000":
            em = discord.Embed(
                title = "SCP-███ - He he watches us all",
                url = "https://scp-secret-laboratory-wiki.fandom.com/wiki/Hubert_Moszka",
                color = 0xe91e63
            )
            em.add_field(name="Object Class", value="Thaumiel", inline=False)
            em.add_field(name="Help", value="We're trapped in his basement, help!", inline=False)
            em.set_thumbnail(url="https://cdn.discordapp.com/attachments/681599779242770444/817006021276336128/HubS.png")
            await ctx.send(embed=em)
        else:
            emb = await self.CromRequest(ctx, scpToSearch, BotSelf=theBot)
            await ctx.send(embed=emb)

    
    async def CromRequest(self, ctx, scp, BotSelf):

        UA = (f"Redbot Cog {BotSelf.name}#{BotSelf.discriminator} - ID {BotSelf.id}") # The lad asked I made sure to identify the bot in the Session via User agents.
        async with aiohttp.ClientSession(headers={'User-Agent': UA}) as session:
            Client = client.GraphQLClient(
                endpoint = "https://api.crom.avn.sh/"
            )
            if str(scp).isdecimal():
                targetSCP = scp
            else:
                targetSCP = str(scp).title()
                
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
            }}""".format(targetScp=targetSCP))
            response: client.GraphQLResponse = await Client.query(request=CromQuery)
            respJson = response.json # Time for the Jason.. Json horde.
            try:
                coreJson = respJson['data']['searchPages'][0] #Save some time
                emTitle = (f"{coreJson['wikidotInfo']['title']}") # Expects a string to return, is the SCP-XXXX
            except:
                em = discord.Embed(
                    title="Error!",
                    description="This isnt a valid SCP name. Try its Article number, or its formal name, if it has one."
                )
                return em

            emName = (f"{coreJson['alternateTitles'][0]['title']}") # Expects to be a strin, is the 'name' e.g. SCP 079's name is "Old AI"
            if emTitle != emName:
                emTrueTitle = (f"{emTitle} - {emName}")
            else:
                emTrueTitle = emTitle
            
            emImage = (f"{coreJson['wikidotInfo']['thumbnailUrl']}") # Expects to be a URL to the main image of the article
            emURL = (f"{coreJson['url']}") # URL to the article itself
            emDesc1 = (f"{coreJson['wikidotInfo']['rating']}") #The articles rating on the wiki
            emDesc2 = (f"{coreJson['attributions'][0]['user']['name']}") # The original Author/submitter.

        EmColour = random.randint(0, 0xffffff)
        em = discord.Embed(
           title=emTrueTitle,
           url=emURL,
           description=(f"Rating: {emDesc1}, Orignal submitter or author: {emDesc2}"),
           color=EmColour
        )
        if emImage != "None": #This is annoying..
            em.set_image(url=emImage)
        else:
            em.set_image(url="https://scp-wiki.wdfiles.com/local--files/component:theme/logo.png")
        em.set_footer(text="Powered by Crom - https://crom.avn.sh/", icon_url="https://pbs.twimg.com/profile_images/1344457914073960452/_V6Ihvs-_400x400.jpg")
        await session.close()
        return em


