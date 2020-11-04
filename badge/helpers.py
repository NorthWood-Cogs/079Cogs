import asyncio
import requests
from redbot.core import Config

async def give_badge(self, type: str, badge_id: str, discord_name: str, given_id: str, discord_id: str):
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
                    "info2": author_id
                }
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
