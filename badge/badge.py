# Fluff
import discord
import asyncio
import requests
import json

# Red
from redbot.core import commands
from redbot.core import Config
from redbot.core import checks

# Helpers - Not quite playing nice yet...
# from .helpers import query_discord_id, give_badge, remove_badge


class Badge(commands.Cog):
    """Commands to give the badge to the Patreon Supporters and Twitch Subs"""

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=5349824615)  # Take a shot
        default_global = {"TOKEN": "123"}
        self.config.register_global(**default_global)
        print('Addon "{}" loaded'.format(self.__class__.__name__))
        self.endpoint = "https://api.scpslgame.com/rest/079/badge.php"

    def is_in_server(guild_id):
        async def predicate(ctx):
            return ctx.guild and ctx.guild.id == guild_id

        return commands.check(predicate)

    @is_in_server(330432627649544202)
    @commands.group(name="badge")
    async def badge(self, ctx):
        """Base class for Badge cog. Hi there! if you're seeing this, you should
        only see the next available step for you!"""
        pass

    @badge.group(name="patreon")
    @commands.has_any_role(
        409844788985331723,  # Janitor
        409845203352944641,  # Scientist
        409845543070597120,  # Major Scientist
        409845714257182721,  # Zone Manager
        409845890740912138,  # Facility Manager
    )
    async def issuepatreonbadge(self, ctx):
        """If you're seeing this, you're entitled to a Patreon badge ingame!
        Follow the steps to get a badge in either the steam version or the discord version."""
        pass

    @issuepatreonbadge.command(name="steam")
    async def patreonsteam(self, ctx, steam_id: str):
        """
        Issue a patreon badge to a given steamID
        """
        if len(steam_id) != 17 or steam_id[:1] != "7":
            await ctx.send("Please use a valid SteamID64")
            return
        discord_query_response = await self.query_discord_id(ctx.message.author.id)
        if discord_query_response == "Badge not issued":
            author = ctx.message.author
            await ctx.send(
                await self.give_badge(
                    "steam", "10", author.name, steam_id, str(author.id)
                )
            )
        else:
            await ctx.send("You currently have an active badge.")

    @issuepatreonbadge.command(name="discord")
    async def patreondiscord(self, ctx):
        """
        Issue a patreon badge to the user's discord account.
        """
        discord_query_response = await self.query_discord_id(ctx.message.author.id)
        if discord_query_response == "Badge not issued":
            str_id = str(ctx.message.author.id)
            author = ctx.message.author
            await ctx.send(
                await self.give_badge("discord", "10", author.name, str_id, str_id)
            )

        else:
            await ctx.send("You currently have an active badge")

    @badge.group(name="twitch")  # Twitch bades start here!
    @commands.has_any_role(
        # Currently only T3 are eligible for the role
        # 781597284050665494,  # T1 Dark
        # 781597284050665495,  # T2 Keneq
        781597284050665496,  # T3 Amida
    )
    async def issuetwitchbadge(self, ctx):
        """If you're seeing this, you're entitled to a Twitch Subscriber badge ingame!
        Follow the steps to get a badge in either the steam version or the discord version."""
        pass

    @issuetwitchbadge.command(name="steam")
    async def twitchsteam(self, ctx, steam_id: str):
        """
        Issues a Twitch Sub badge to a given steamID
        """
        if len(steam_id) != 17 or steam_id[:1] != "7":
            await ctx.send("Please use a valid SteamID64")
            return
        discord_query_response = await self.query_discord_id(ctx.message.author.id)
        if discord_query_response == "Badge not issued":
            await ctx.send(
                await self.give_badge(
                    "steam",
                    "9",
                    ctx.message.author.name,
                    steam_id,
                    str(ctx.message.author.id),
                )
            )
        else:
            await ctx.send("You currently have an active badge.")

    @issuetwitchbadge.command(name="discord")
    async def twitchdiscord(self, ctx):
        """
        Issue a Twitch Sub badge to the user's discord account.
        """
        discord_query_response = await self.query_discord_id(ctx.message.author.id)
        if discord_query_response == "Badge not issued":
            str_id = str(ctx.message.author.id)
            author = ctx.message.author
            await ctx.send(
                await self.give_badge("discord", "9", author.name, str_id, str_id)
            )

            await ctx.send(issue_request.text)
        else:
            await ctx.send("You currently have an active badge")

    @badge.command(name="revoke")
    @commands.has_any_role(
        "Patreon level - Major Scientist",
        "Patreon level - Zone Manager",
        "Patreon level - Facility Manager",
        "Twitch Subscriber: Tier 2",
        "Twitch Subscriber: Tier 3",
    )
    async def revokebadge(self, ctx):
        """
        Revokes a patreon badge from yourself.
        """
        await ctx.send(
            await self.remove_badge(
                discord_id=str(ctx.message.author.id),
                discord_name=ctx.message.author.name,
            )
        )

    @checks.is_owner()  # Dear Masonic, remember what this is. I saw you added that pokey owner check before. It dissapoints me.
    @commands.command()
    async def settoken(self, ctx, arg):
        await self.config.TOKEN.set(arg)

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        if before.guild.id == 330432627649544202:
            server = before.guild
            # TODO: Make these cog-wide
            patreon_roles = [
                discord.utils.get(
                    server.roles, name="Patreon level - Facility Manager"
                ),
                discord.utils.get(server.roles, name="Patreon level - Zone Manager"),
                discord.utils.get(server.roles, name="Patreon level - Major Scientist"),
                discord.utils.get(server.roles, name="Twitch Subscriber: Tier 2"),
                discord.utils.get(server.roles, name="Twitch Subscriber: Tier 3"),
            ]
            patreon_role = next((i for i in before.roles if i in patreon_roles), None)
            if patreon_role is not None:
                has_role_after = False
                for j in after.roles:
                    if j == patreon_role:
                        has_role_after = True
                        break
                if not has_role_after:
                    await self.remove_badge(
                        discord_id=after.id, discord_name=after.name
                    )

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        if member.guild.id == 330432627649544202:
            await self.remove_badge(discord_id=member.id, discord_name=member.name)

    async def give_badge(
        self,
        type: str,
        badge_id: str,
        discord_name: str,
        given_id: str,
        discord_id: str,
    ):
        if type == "discord":
            issue_request = requests.post(
                self.endpoint,
                data={
                    "token": await self.config.TOKEN(),
                    "action": "issue",
                    "id": (given_id + "@discord"),
                    "badge": badge_id,
                    "info": discord_name,
                    "info2": given_id,
                },
            )
            return "Badge Applied!"
        if type == "steam":
            issue_request = requests.post(
                self.endpoint,
                data={
                    "token": await self.config.TOKEN(),
                    "action": "issue",
                    "id": (given_id + "@steam"),
                    "badge": badge_id,
                    "info": discord_name,
                    "info2": discord_id,
                },
            )
            return "Badge Applied!"
        else:
            return "Badge type wasn't valid, somehow. Please contact a Bot Engineer!"

    async def remove_badge(self, discord_id: str, discord_name: str):
        """
        Attempts to remove a user's badge
        """
        status = await self.query_discord_id(discord_id)
        if status != "Badge not issued":
            query_json = json.loads(status)
            query_info2 = query_json["info2"]
            query_userid = query_json["userid"]
            author_id = str(discord_id)
            if author_id == query_info2:
                revoke_query = requests.post(
                    self.endpoint,
                    data={
                        "token": await self.config.TOKEN(),
                        "action": "issue",
                        "badge": "",
                        "id": query_userid,
                        "info": discord_name,
                        "info2": author_id,
                    },
                )
                return revoke_query.text
            else:
                return "An error has occurred. Please tell a Patreon Representative or a Global Moderator."
        else:
            return "It seems that you don't have a badge!"

    async def query_discord_id(self, discord_id):
        query = requests.post(
            self.endpoint,
            data={
                "token": await self.config.TOKEN(),
                "action": "queryDiscordId",
                "id": discord_id,
            },
        )
        return query.text
