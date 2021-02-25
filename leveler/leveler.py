import asyncio
import contextlib
import logging
import operator
import os
import platform
import random
import re
import string
import textwrap
import time
from asyncio import TimeoutError
from copy import copy
from datetime import datetime, timedelta

from discord.ext.commands import BotMissingPermissions
from tabulate import tabulate
from io import BytesIO
from typing import Union

import aiohttp
import discord
import math
import numpy
import scipy
import scipy.cluster
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps
from discord.utils import find
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import errors as mongoerrors
from redbot.core.bot import Red
from redbot.core import Config, bank, checks, commands
from redbot.core.data_manager import bundled_data_path, cog_data_path
from redbot.core.utils.chat_formatting import box, pagify
from redbot.core.utils.menus import DEFAULT_CONTROLS, menu
from redbot.core.utils.predicates import MessagePredicate


log = logging.getLogger("red.aikaterna.leveler")


async def non_global_bank(ctx):
    return not await bank.is_global()


class Leveler(commands.Cog):
    """A level up thing with image generation!"""

    def __init__(self, bot: Red):
        self.bot = bot

        # fonts
        self.font_file = f"{bundled_data_path(self)}/font.ttf"
        self.font_bold_file = f"{bundled_data_path(self)}/font_bold.ttf"
        self.font_unicode_file = f"{bundled_data_path(self)}/unicode.ttf"
        self.config = Config.get_conf(self, identifier=2733301001)
        default_mongodb = {
            "host": "localhost",
            "port": 27017,
            "username": None,
            "password": None,
            "db_name": "leveler",
        }
        default_global = {
            "bg_price": 0,
            "badge_type": "circles",
            "removed_backgrounds": {"profile": [], "rank": [], "levelup": []},
            "backgrounds": {"profile": {}, "rank": {}, "levelup": {}},
            "xp": [15, 20],
            "default_profile": "http://i.imgur.com/8T1FUP5.jpg",
            "default_rank": "http://i.imgur.com/SorwIrc.jpg",
            "default_levelup": "http://i.imgur.com/eEFfKqa.jpg",
            "rep_price": 0,
        }
        default_guild = {
            "disabled": False,
            "lvl_msg": False,
            "mentions": True,
            "text_only": False,
            "private_lvl_message": False,
            "lvl_msg_lock": None,
            "msg_credits": 0,
            "ignored_channels": [],
        }
        self.config.init_custom("MONGODB", -1)
        self.config.register_custom("MONGODB", **default_mongodb)
        self.config.register_global(**default_global)
        self.config.register_guild(**default_guild)

        self._db_ready = False
        self.client = None
        self.db = None
        self.session = aiohttp.ClientSession(loop=self.bot.loop)
        self._message_tasks = []
        self._message_task_processor = asyncio.create_task(self.process_tasks())
        self._message_task_processor.add_done_callback(self._task_error_logger)

    async def initialize(self):
        await self._connect_to_mongo()

    async def _connect_to_mongo(self):
        if self._db_ready:
            self._db_ready = False
        self._disconnect_mongo()
        config = await self.config.custom("MONGODB").all()
        log.debug(f"Leveler is connecting to a MongoDB server at: {config}")
        try:
            self.client = AsyncIOMotorClient(**{k: v for k, v in config.items() if not k == "db_name"})
            await self.client.server_info()
            self.db = self.client[config["db_name"]]
            self._db_ready = True
        except (
            mongoerrors.ServerSelectionTimeoutError,
            mongoerrors.ConfigurationError,
            mongoerrors.OperationFailure,
        ) as error:
            log.exception(
                "Can't connect to the MongoDB server.\nFollow instructions on Git/online to install MongoDB.",
                exc_info=error,
            )
            self.client = None
            self.db = None
        return self.client

    def _disconnect_mongo(self):
        if self.client:
            self.client.close()

    async def cog_check(self, ctx):
        if (ctx.command.parent is self.levelerset) or ctx.command is self.levelerset:
            return True
        return self._db_ready

    def cog_unload(self):
        self.bot.loop.create_task(self.session.close())
        if self._message_task_processor:
            self._message_task_processor.cancel()
        self._disconnect_mongo()

    def _task_error_logger(self, fut):
        """Logs errors in the _message_task_processor task."""
        try:
            fut.result()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            log.critical("The leveler task encountered an unexpected error and has stopped.\n", exc_info=e)

    @property
    def DEFAULT_BGS(self):
        return {
            "profile": {
                "alice": "http://i.imgur.com/MUSuMao.png",
                "bluestairs": "http://i.imgur.com/EjuvxjT.png",
                "lamp": "http://i.imgur.com/0nQSmKX.jpg",
                "coastline": "http://i.imgur.com/XzUtY47.jpg",
                "redblack": "http://i.imgur.com/74J2zZn.jpg",
                "default": "http://i.imgur.com/8T1FUP5.jpg",
                "iceberg": "http://i.imgur.com/8KowiMh.png",
                "miraiglasses": "http://i.imgur.com/2Ak5VG3.png",
                "miraikuriyama": "http://i.imgur.com/jQ4s4jj.png",
                "mountaindawn": "http://i.imgur.com/kJ1yYY6.jpg",
                "waterlilies": "http://i.imgur.com/qwdcJjI.jpg",
                "greenery": "http://i.imgur.com/70ZH6LX.png",
                "abstract": "http://i.imgur.com/70ZH6LX.png",
            },
            "rank": {
                "aurora": "http://i.imgur.com/gVSbmYj.jpg",
                "default": "http://i.imgur.com/SorwIrc.jpg",
                "nebula": "http://i.imgur.com/V5zSCmO.jpg",
                "mountain": "http://i.imgur.com/qYqEUYp.jpg",
                "city": "http://i.imgur.com/yr2cUM9.jpg",
            },
            "levelup": {"default": "http://i.imgur.com/eEFfKqa.jpg"},
        }

    async def get_backgrounds(self):
        ret = self.DEFAULT_BGS
        removal_dict = await self.config.removed_backgrounds()

        for bg_type, removals in removal_dict.items():
            for rem in removals:
                ret[bg_type].pop(rem, None)

        user_backgrounds = await self.config.backgrounds()

        for bg_type, update_with in user_backgrounds.items():
            ret[bg_type].update(update_with)

        return ret

    async def delete_background(self, bg_type: str, bg_name: str):

        found = False
        async with self.config.backgrounds() as bgs:
            if bg_name in bgs[bg_type]:
                found = True
                del bgs[bg_type][bg_name]

        try:
            _k = self.DEFAULT_BGS[bg_type][bg_name]
        except KeyError:
            if not found:
                raise
        else:
            async with self.config.removed_backgrounds() as rms:
                if bg_name not in rms[bg_type]:
                    rms[bg_type].append(bg_name)
    
    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.command(name="reps")
    @commands.guild_only()
    async def reps(self, ctx, *, user: discord.Member = None):
        if user is None:
            user = ctx.author
        if user.bot:
            ctx.command.reset_cooldown(ctx)
            await ctx.send("Bots don't have a reputation, y'know.")
        server = user.guild

            # creates user if doesn't exist
        await self._create_user(user, server)
        userinfo = await db.users.find_one({"user_id": str(user.id)})

        # check if disabled
        if await self.config.guild(ctx.guild).disabled():
            await ctx.send("**Leveler commands for this server are disabled!**")
            return
        userinfo = await db.users.find_one({"user_id": str(user.id)})
        userinfo["rep"]
        repCount = userinfo["rep"]
        await ctx.send(f"{user.name} has {repCount} reputation Points.")

    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.command(name="profile")
    @commands.bot_has_permissions(attach_files=True)
    @commands.guild_only()
    async def profile(self, ctx, *, user: discord.Member = None):
        """Displays a user profile."""
        if user is None:
            user = ctx.message.author
        channel = ctx.message.channel
        server = user.guild
        curr_time = time.time()

        # creates user if doesn't exist
        await self._create_user(user, server)
        userinfo = await self.db.users.find_one({"user_id": str(user.id)})

        # check if disabled
        if await self.config.guild(ctx.guild).disabled():
            await ctx.send("**Leveler commands for this server are disabled!**")
            return

        # no cooldown for text only
        if await self.config.guild(ctx.guild).text_only():
            em = await self.profile_text(user, server, userinfo)
            await channel.send(embed=em)
        else:
            async with ctx.channel.typing():
                file = await self.draw_profile(user, server)
                await channel.send("**User profile for {}**".format(await self._is_mention(user)), file=file)
            await self.db.users.update_one(
                {"user_id": str(user.id)}, {"$set": {"profile_block": curr_time}}, upsert=True
            )

    async def profile_text(self, user, server, userinfo):
        def test_empty(text):
            if not text:
                return "None"
            else:
                return text

        em = discord.Embed(colour=user.colour)
        em.add_field(name="Title:", value=test_empty(userinfo["title"]))
        em.add_field(name="Reps:", value=userinfo["rep"])
        global_ranking = await self._find_global_rank(user)
        if global_ranking:
            em.add_field(name="Global Rank:", value=f"#{global_ranking}")
        em.add_field(name="Server Rank:", value=f"#{await self._find_server_rank(user, server)}")
        em.add_field(name="Server Level:", value=format(userinfo["servers"][str(server.id)]["level"]))
        em.add_field(name="Total Exp:", value=userinfo["total_exp"])
        em.add_field(name="Server Exp:", value=await self._find_server_exp(user, server))
        u_credits = await bank.get_balance(user)
        em.add_field(name="Credits: ", value=f"${u_credits}")
        em.add_field(name="Info: ", value=test_empty(userinfo["info"]))
        em.add_field(name="Badges: ", value=test_empty(", ".join(userinfo["badges"])).replace("_", " "))
        em.set_author(name=f"Profile for {user.name}", url=user.avatar_url)
        em.set_thumbnail(url=user.avatar_url)
        return em

    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.bot_has_permissions(attach_files=True)
    @commands.command()
    @commands.guild_only()
    async def rank(self, ctx, user: discord.Member = None):
        """Displays a user's rank card."""
        if user is None:
            user = ctx.message.author
        channel = ctx.message.channel
        server = user.guild
        curr_time = time.time()

        # creates user if doesn't exist
        await self._create_user(user, server)
        userinfo = await self.db.users.find_one({"user_id": str(user.id)})

        # check if disabled
        if await self.config.guild(ctx.guild).disabled():
            await ctx.send("**Leveler commands for this server are disabled!**")
            return

        # no cooldown for text only
        if await self.config.guild(server).text_only():
            em = await self.rank_text(user, server, userinfo)
            await channel.send("", embed=em)
        else:
            async with ctx.typing():
                file = await self.draw_rank(user, server)
                await ctx.send(f"**Ranking & Statistics for {await self._is_mention(user)}**", file=file)
            await self.db.users.update_one(
                {"user_id": str(user.id)}, {"$set": {"rank_block".format(server.id): curr_time}}, upsert=True,
            )

    @rank.error
    async def rank_error(self, ctx, error):
        if isinstance(error, BotMissingPermissions):
            await ctx.send("I need ``attach_files``-permissions =)")

    async def rank_text(self, user, server, userinfo):
        em = discord.Embed(colour=user.colour)
        em.add_field(name="Server Rank", value=f"#{await self._find_server_rank(user, server)}")
        em.add_field(name="Reps", value=userinfo["rep"])
        em.add_field(name="Server Level", value=userinfo["servers"][str(server.id)]["level"])
        em.add_field(name="Server Exp", value=await self._find_server_exp(user, server))
        em.set_author(name=f"Rank and Statistics for {user.name}", url=user.avatar_url)
        em.set_thumbnail(url=user.avatar_url)
        return em

    # should the user be mentioned based on settings?
    async def _is_mention(self, user):
        if await self.config.guild(user.guild).mentions():
            return user.mention
        else:
            return user.name

    @commands.cooldown(1, 10, commands.BucketType.guild)
    @commands.bot_has_permissions(embed_links=True)
    @commands.command(usage="[page] [-rep] [-global]")
    @commands.guild_only()
    async def top(self, ctx, *options):
        """
        Displays the leaderboard.

        Add the `-global` parameter for global and `-rep` for reputation.

        Examples:
        `[p]top`
        - Displays the server leaderboard
        `[p]top -rep`
        - Displays the server reputation leaderboard
        `[p]top -global`
        - Displays the global leaderboard
        `[p]top -rep -global`
        - Displays the global reputation leaderboard
        """
        if await self.config.guild(ctx.guild).disabled():
            await ctx.send("**Leveler commands for this server are disabled!**")
            return

        user = ctx.author
        server = ctx.guild
        q = f"servers.{server.id}"
        space = "\N{EN SPACE}"
        guild_ids = [str(x.id) for x in ctx.guild.members]
        await self._create_user(user, server)

        async with ctx.typing():
            users = []
            user_stat = None
            if "-rep" in options and "-global" in options:
                title = "Global Rep Leaderboard for {}\n".format(self.bot.user.name)
                async for userinfo in self.db.users.find(({"rep": {"$gte": 1}})).sort("rep", -1).limit(300):
                    await asyncio.sleep(0)
                    try:
                        users.append((userinfo["username"], userinfo["rep"]))
                    except KeyError:
                        users.append((str(int(userinfo["user_id"])), userinfo["rep"]))

                    if str(user.id) == userinfo["user_id"]:
                        user_stat = userinfo["rep"]

                board_type = "Rep"
                global_rep_rank = await self._find_global_rep_rank(user)
                if global_rep_rank:
                    footer_text = f"Your Rank: {global_rep_rank}                 {board_type}: {user_stat}"
                else:
                    footer_text = f"{space*40}"
                icon_url = self.bot.user.avatar_url
            elif "-global" in options:
                title = "Global Exp Leaderboard for {}\n".format(self.bot.user.name)
                async for userinfo in self.db.users.find(({"total_exp": {"$gte": 100}})).sort("total_exp", -1).limit(
                    300
                ):
                    await asyncio.sleep(0)
                    try:
                        users.append((userinfo["username"], userinfo["total_exp"]))
                    except KeyError:
                        users.append((str(int(userinfo["user_id"])), userinfo["total_exp"]))

                    if str(user.id) == userinfo["user_id"]:
                        user_stat = userinfo["total_exp"]

                board_type = "Points"
                global_ranking = await self._find_global_rank(user)
                if global_ranking:
                    footer_text = f"Your Rank: {global_ranking}                 {board_type}: {user_stat}"
                else:
                    footer_text = f"{space*40}"
                icon_url = self.bot.user.avatar_url
            elif "-rep" in options:
                title = "Rep Leaderboard for {}\n".format(server.name)
                async for userinfo in self.db.users.find(
                    {"$and": [{q: {"$exists": "true"}}, {"rep": {"$gte": 1}}]}
                ).sort("rep", -1):
                    await asyncio.sleep(0)
                    if userinfo["user_id"] in guild_ids:
                        try:
                            users.append((userinfo["username"], userinfo["rep"]))
                        except KeyError:
                            users.append((str(int(userinfo["user_id"])), userinfo["rep"]))

                    if str(user.id) == userinfo["user_id"]:
                        user_stat = userinfo["rep"]

                board_type = "Rep"
                footer_text = "Your Rank: {}               {}: {}".format(
                    await self._find_server_rep_rank(user, server), board_type, user_stat,
                )
                icon_url = server.icon_url
            else:
                title = "Exp Leaderboard for {}\n".format(server.name)
                async for userinfo in self.db.users.find({q: {"$exists": "true"}}):
                    await asyncio.sleep(0)
                    if userinfo["user_id"] in guild_ids:
                        server_exp = 0
                        # generate total xp gain for each level gained
                        for i in range(userinfo["servers"][str(server.id)]["level"]):
                            await asyncio.sleep(0)
                            server_exp += self._required_exp(i)
                        # add current non-completed level exp to count
                        server_exp += userinfo["servers"][str(server.id)]["current_exp"]
                        try:
                            users.append((userinfo["username"], server_exp))
                        except:
                            users.append((str(int(userinfo["user_id"])), server_exp))
                board_type = "Points"
                footer_text = "Your Rank: {}                {}: {}".format(
                    await self._find_server_rank(user, server), board_type, await self._find_server_exp(user, server),
                )
                icon_url = server.icon_url
            sorted_list = sorted(users, key=operator.itemgetter(1), reverse=True)

            if not sorted_list:
                return await ctx.send("**There are no results to display.**")

            # multiple page support
            page = 1
            per_page = 15
            pages = math.ceil(len(sorted_list) / per_page)
            for option in options:
                if str(option).isdigit():
                    if page >= 1 and int(option) <= pages:
                        page = int(str(option))
                    else:
                        await ctx.send("**Please enter a valid page number! (1 - {})**".format(str(pages)))
                        return
                    break

            msg = ""
            rank = 1 + per_page * (page - 1)
            start_index = per_page * page - per_page
            end_index = per_page * page
            top_user_value = 8 + len(str(sorted_list[start_index:end_index][0][1])) + 4

            async for single_user in self.asyncit(sorted_list[start_index:end_index]):
                await asyncio.sleep(0)
                label = "   "
                rank_text = f"{rank:<2}"
                label_text = f"{label:<2}"
                separator_text = f"{'➤':<3}"
                padding = len(rank_text), len(label_text), len(separator_text) + 1
                point_text = f"# {'{}: {}'.format(board_type, single_user[1]).ljust(top_user_value, ' ')}"
                nam_text = f"{self._truncate_text(single_user[0], 18):<5}\n"

                msg += rank_text + label_text + separator_text + point_text + nam_text
                rank += 1
            separator = "-" * len(footer_text)
            rank_pad, level_pad, extra_pad = padding
            msg += f"{separator}\n{footer_text}\nPage: {page}/{pages}"
            em = discord.Embed(description=box(msg), colour=user.colour)
            em.set_author(name=title, icon_url=icon_url)

            await ctx.send(embed=em)

    @commands.cooldown(1, 30, commands.BucketType.user)
    @commands.command()
    @commands.guild_only()
    async def rep(self, ctx, user: discord.Member = None):
        """Gives a reputation point to a designated player."""
        org_user = ctx.author
        server = ctx.guild
        # creates user if doesn't exist
        await self._create_user(org_user, server)
        if user:
            await self._create_user(user, server)
        org_userinfo = await self.db.users.find_one({"user_id": str(org_user.id)})
        curr_time = time.time()

        if await self.config.guild(ctx.guild).disabled():
            await ctx.send("**Leveler commands for this server are disabled!**")
            return
        if user and user.id == org_user.id:
            await ctx.send("**You can't give a rep to yourself!**")
            return
        if user and user.bot:
            await ctx.send("**You can't give a rep to a bot!**")
            return
        if "rep_block" not in org_userinfo:
            org_userinfo["rep_block"] = 0

        delta = float(curr_time) - float(org_userinfo["rep_block"])
        if user and delta >= 43200.0 and delta > 0:
            userinfo = await self.db.users.find_one({"user_id": str(user.id)})
            await self.db.users.update_one({"user_id": str(org_user.id)}, {"$set": {"rep_block": curr_time}})
            await self.db.users.update_one({"user_id": str(user.id)}, {"$set": {"rep": userinfo["rep"] + 1}})
            await ctx.send("**You have just given {} a reputation point!**".format(await self._is_mention(user)))
        else:
            # calculate time left
            seconds = 43200 - delta
            if seconds < 0:
                await ctx.send("**You can give a rep!**")
                return

            m, s = divmod(seconds, 60)
            h, m = divmod(m, 60)
            await ctx.send(
                "**You need to wait {} hours, {} minutes, and {} seconds until you can give reputation again!**".format(
                    int(h), int(m), int(s)
                )
            )

    @commands.cooldown(1, 30, commands.BucketType.user)
    @commands.command()
    @commands.guild_only()
    async def represet(self, ctx):
        """Reset your rep cooldown for a price."""
        if await self.config.guild(ctx.guild).disabled():
            return await ctx.send("**Leveler commands for this server are disabled!**")

        rep_price = await self.config.rep_price()
        if rep_price == 0:
            return await ctx.send("**Rep resets are not set up. Ask the bot owner to provide a rep reset cost.**")

        user = ctx.author
        server = ctx.guild
        # creates user if doesn't exist
        await self._create_user(user, server)

        userinfo = await self.db.users.find_one({"user_id": str(user.id)})
        if "rep_block" not in userinfo:
            userinfo["rep_block"] = 0

        curr_time = time.time()
        delta = float(curr_time) - float(userinfo["rep_block"])
        if delta >= 43200.0 and delta > 0:
            return await ctx.send("**You can give a rep without resetting your rep cooldown!**")

        if not await bank.can_spend(user, rep_price):
            await ctx.send("**Insufficient funds. Rep resets cost: ${}**".format(rep_price))
        else:
            currency_name = await bank.get_currency_name(ctx.guild)
            await ctx.send(
                "**{}, you are about to reset your rep cooldown for `{}` {}. Confirm by typing **`yes`.".format(
                    await self._is_mention(user), rep_price, currency_name
                )
            )
            pred = MessagePredicate.yes_or_no(ctx)
            try:
                await self.bot.wait_for("message", check=pred, timeout=15)
            except TimeoutError:
                return await ctx.send("**Purchase canceled.**")
            if not pred.result:
                return await ctx.send("**Purchase canceled.**")

            await bank.withdraw_credits(user, rep_price)
            await self.db.users.update_one(
                {"user_id": str(user.id)}, {"$set": {"rep_block": (float(curr_time) - 43201.0)}}
            )
            await ctx.send("**You have reset your rep cooldown!**")

    @commands.command()
    @commands.bot_has_permissions(embed_links=True)
    @commands.guild_only()
    async def lvlinfo(self, ctx, user: discord.Member = None):
        """Gives more specific details about a user's profile."""
        if not user:
            user = ctx.author
        server = ctx.guild
        userinfo = await self.db.users.find_one({"user_id": str(user.id)})

        if await self.config.guild(ctx.guild).disabled():
            await ctx.send("**Leveler commands for this server are disabled!**")
            return

        # creates user if doesn't exist
        await self._create_user(user, server)
        msg = ""
        msg += f"Name: {user.name}\n"
        msg += f"Title: {userinfo['title']}\n"
        msg += f"Reps: {userinfo['rep']}\n"
        msg += f"Server Level: {userinfo['servers'][str(server.id)]['level']}\n"
        total_server_exp = 0
        for i in range(userinfo["servers"][str(server.id)]["level"]):
            await asyncio.sleep(0)
            total_server_exp += self._required_exp(i)
        total_server_exp += userinfo["servers"][str(server.id)]["current_exp"]
        msg += f"Server Exp: {total_server_exp}\n"
        msg += f"Total Exp: {userinfo['total_exp']}\n"
        msg += f"Info: {userinfo['info']}\n"
        msg += f"Profile background: {userinfo['profile_background']}\n"
        msg += f"Rank background: {userinfo['rank_background']}\n"
        msg += f"Levelup background: {userinfo['levelup_background']}\n"
        if "profile_info_color" in userinfo.keys() and userinfo["profile_info_color"]:
            msg += f"Profile info color: {self._rgb_to_hex(userinfo['profile_info_color'])}\n"
        if "profile_exp_color" in userinfo.keys() and userinfo["profile_exp_color"]:
            msg += f"Profile exp color: {self._rgb_to_hex(userinfo['profile_exp_color'])}\n"
        if "rep_color" in userinfo.keys() and userinfo["rep_color"]:
            msg += f"Rep section color: {self._rgb_to_hex(userinfo['rep_color'])}\n"
        if "badge_col_color" in userinfo.keys() and userinfo["badge_col_color"]:
            msg += f"Badge section color: {self._rgb_to_hex(userinfo['badge_col_color'])}\n"
        if "rank_info_color" in userinfo.keys() and userinfo["rank_info_color"]:
            msg += f"Rank info color: {self._rgb_to_hex(userinfo['rank_info_color'])}\n"
        if "rank_exp_color" in userinfo.keys() and userinfo["rank_exp_color"]:
            msg += f"Rank exp color: {self._rgb_to_hex(userinfo['rank_exp_color'])}\n"
        if "levelup_info_color" in userinfo.keys() and userinfo["levelup_info_color"]:
            msg += f"Level info color: {self._rgb_to_hex(userinfo['levelup_info_color'])}\n"
        msg += "Badges: "
        msg += ", ".join(userinfo["badges"])

        em = discord.Embed(description=msg, colour=user.colour)
        em.set_author(name=f"Profile Information for {user.name}", icon_url=user.avatar_url)
        await ctx.send(embed=em)

    @staticmethod
    def _rgb_to_hex(rgb):
        rgb = tuple(rgb[:3])
        return "#%02x%02x%02x" % rgb

    @checks.is_owner()
    @commands.group()
    async def levelerset(self, ctx):
        """
        MongoDB server configuration options.
        
        Use this command in DMs to see current settings.
        """
        if not ctx.invoked_subcommand and ctx.channel.type == discord.ChannelType.private:
            settings = [
                (setting.replace("_", " ").title(), value)
                for setting, value in (await self.config.custom("MONGODB").get_raw()).items()
                if value
            ]
            await ctx.send(box(tabulate(settings, tablefmt="plain")))

    @levelerset.command()
    async def host(self, ctx, host: str = "localhost"):
        """Set the MongoDB server host."""
        await self.config.custom("MONGODB").host.set(host)
        message = await ctx.send(f"MongoDB host set to {host}.\nNow trying to connect to the new host...")
        client = await self._connect_to_mongo()
        if not client:
            return await message.edit(
                content=message.content.replace("Now trying to connect to the new host...", "")
                + "Failed to connect. Please try again with a valid host."
            )
        await message.edit(content=message.content.replace("Now trying to connect to the new host...", ""))

    @levelerset.command()
    async def port(self, ctx, port: int = 27017):
        """Set the MongoDB server port."""
        await self.config.custom("MONGODB").port.set(port)
        message = await ctx.send(f"MongoDB port set to {port}.\nNow trying to connect to the new port...")
        client = await self._connect_to_mongo()
        if not client:
            return await message.edit(
                content=message.content.replace("Now trying to connect to the new port...", "")
                + "Failed to connect. Please try again with a valid port."
            )
        await message.edit(content=message.content.replace("Now trying to connect to the new port...", ""))

    @levelerset.command(aliases=["creds"])
    async def credentials(self, ctx, username: str = None, password: str = None):
        """Set the MongoDB server credentials."""
        await self.config.custom("MONGODB").username.set(username)
        await self.config.custom("MONGODB").password.set(password)
        message = await ctx.send("MongoDB credentials set.\nNow trying to connect...")
        client = await self._connect_to_mongo()
        if not client:
            return await message.edit(
                content=message.content.replace("Now trying to connect...", "")
                + "Failed to connect. Please try again with valid credentials."
            )
        await message.edit(content=message.content.replace("Now trying to connect...", ""))

    @levelerset.command()
    async def dbname(self, ctx, dbname: str = "leveler"):
        """Set the MongoDB db name."""
        await self.config.custom("MONGODB").db_name.set(dbname)
        message = await ctx.send("MongoDB db name set.\nNow trying to connect...")
        client = await self._connect_to_mongo()
        if not client:
            return await message.edit(
                content=message.content.replace("Now trying to connect...", "")
                + "Failed to connect. Please try again with a valid db name."
            )
        await message.edit(content=message.content.replace("Now trying to connect...", ""))

    @commands.group(name="lvlset")
    @commands.guild_only()
    async def lvlset(self, ctx):
        """Profile configuration options."""
        pass

    @lvlset.group(name="profile")
    async def profileset(self, ctx):
        """Profile options."""
        pass

    @lvlset.group(name="rank")
    async def rankset(self, ctx):
        """Rank options."""
        pass

    @lvlset.group(name="levelup")
    async def levelupset(self, ctx):
        """Level-up options."""
        pass

    @profileset.command(name="color")
    async def profilecolors(self, ctx, section: str, color: str):
        """
        Set colors on the profile card.
        
        **section** can be one of: `exp` `rep` `badge` `info` `all`
        `exp` is the experience bar and the xp numbers above the name
        `rep` is the bar holding the rep number under the user's profile picture
        `badge` is the backdrop of the badge area on the left of the profile
        `info` is the backdrop of the text info areas
        `all` is a combination of all of the above

        **color** can be one of: `default` `white` `auto` or a hex code formatted like `#990000`
        `default` will reset all profile parts to the default colors
        `white` is used for a greyish transparent white, can be better than #FFFFFF
        `auto` automatically chooses the appropriate colors based on the profile background image
        """
        user = ctx.author
        server = ctx.guild
        # creates user if doesn't exist
        await self._create_user(user, server)
        userinfo = await self.db.users.find_one({"user_id": str(user.id)})

        section = section.lower()
        default_info_color = (30, 30, 30, 200)
        white_info_color = (150, 150, 150, 180)
        default_rep = (92, 130, 203, 230)
        default_badge = (128, 151, 165, 230)
        default_exp = (255, 255, 255, 230)
        default_a = 200

        if await self.config.guild(ctx.guild).disabled():
            await ctx.send("**Leveler commands for this server are disabled!**")
            return

        if await self.config.guild(ctx.guild).text_only():
            await ctx.send("**Leveler is in text-only mode.**")
            return

        # get correct section for self.db query
        if section == "rep":
            section_name = "rep_color"
        elif section == "exp":
            section_name = "profile_exp_color"
        elif section == "badge":
            section_name = "badge_col_color"
        elif section == "info":
            section_name = "profile_info_color"
        elif section == "all":
            section_name = "all"
        else:
            await ctx.send("**Not a valid section. (rep, exp, badge, info, all)**")
            return

        # get correct color choice
        if color == "auto":
            if section == "exp":
                color_ranks = [random.randint(2, 3)]
            elif section == "rep":
                color_ranks = [random.randint(2, 3)]
            elif section == "badge":
                color_ranks = [0]  # most prominent color
            elif section == "info":
                color_ranks = [random.randint(0, 1)]
            elif section == "all":
                color_ranks = [random.randint(2, 3), random.randint(2, 3), 0, random.randint(0, 2)]
            else:
                return

            hex_colors = await self._auto_color(ctx, userinfo["profile_background"], color_ranks)
            set_color = []
            for hex_color in hex_colors:
                await asyncio.sleep(0)
                color_temp = self._hex_to_rgb(hex_color, default_a)
                set_color.append(color_temp)

        elif color == "white":
            set_color = [white_info_color]
        elif color == "default":
            if section == "exp":
                set_color = [default_exp]
            elif section == "rep":
                set_color = [default_rep]
            elif section == "badge":
                set_color = [default_badge]
            elif section == "info":
                set_color = [default_info_color]
            elif section == "all":
                set_color = [default_exp, default_rep, default_badge, default_info_color]
            else:
                return
        elif self._is_hex(color):
            set_color = [self._hex_to_rgb(color, default_a)]
        else:
            await ctx.send("**Not a valid color. Use** `default`, `white`, **a valid hex code formatted like** `#990000`, **or** `auto` **for automatic**.")
            return

        if section == "all":
            if len(set_color) == 1:
                await self.db.users.update_one(
                    {"user_id": str(user.id)},
                    {
                        "$set": {
                            "profile_exp_color": set_color[0],
                            "rep_color": set_color[0],
                            "badge_col_color": set_color[0],
                            "profile_info_color": set_color[0],
                        }
                    },
                )
            elif color == "default":
                await self.db.users.update_one(
                    {"user_id": str(user.id)},
                    {
                        "$set": {
                            "profile_exp_color": default_exp,
                            "rep_color": default_rep,
                            "badge_col_color": default_badge,
                            "profile_info_color": default_info_color,
                        }
                    },
                )
            elif color == "auto":
                await self.db.users.update_one(
                    {"user_id": str(user.id)},
                    {
                        "$set": {
                            "profile_exp_color": set_color[0],
                            "rep_color": set_color[1],
                            "badge_col_color": set_color[2],
                            "profile_info_color": set_color[3],
                        }
                    },
                )
            await ctx.send("**Colors for profile set.**")
        else:
            # print("update one")
            await self.db.users.update_one({"user_id": str(user.id)}, {"$set": {section_name: set_color[0]}})
            await ctx.send("**Color for profile {} set.**".format(section))

    @rankset.command(name="color")
    @commands.guild_only()
    async def rankcolors(self, ctx, section: str, color: str = None):
        """
        Set colors on the rank card.
        
        **section** can be one of: `exp` `info` `all`
        `exp` is the experience bar around the user's profile picture
        `info` is the backdrop of the text info areas
        `all` is a combination of all of the above

        **color** can be one of: `default` `white` `auto` or a hex code formatted like `#990000`
        `default` will reset all rank parts to the default colors
        `white` is used for a greyish transparent white, can be better than #FFFFFF
        `auto` automatically chooses the appropriate colors based on the rank background image
        """
        user = ctx.author
        server = ctx.guild
        # creates user if doesn't exist
        await self._create_user(user, server)
        userinfo = await self.db.users.find_one({"user_id": str(user.id)})

        section = section.lower()
        default_info_color = (30, 30, 30, 200)
        white_info_color = (150, 150, 150, 180)
        default_exp = (255, 255, 255, 230)
        default_rep = (92, 130, 203, 230)
        default_badge = (128, 151, 165, 230)
        default_a = 200

        if await self.config.guild(ctx.guild).disabled():
            await ctx.send("**Leveler commands for this server are disabled!**")
            return

        if await self.config.guild(ctx.guild).text_only():
            await ctx.send("**Leveler is in text-only mode.**")
            return

        # get correct section for db query
        if section == "exp":
            section_name = "rank_exp_color"
        elif section == "info":
            section_name = "rank_info_color"
        elif section == "all":
            section_name = "all"
        else:
            await ctx.send("**Not a valid section. (exp, info, all)**")
            return

        # get correct color choice
        if color == "auto":
            if section == "exp":
                color_ranks = [random.randint(2, 3)]
            elif section == "info":
                color_ranks = [random.randint(0, 1)]
            elif section == "all":
                color_ranks = [random.randint(2, 3), random.randint(0, 1)]
            else:
                return

            hex_colors = await self._auto_color(ctx, userinfo["rank_background"], color_ranks)
            set_color = []
            for hex_color in hex_colors:
                await asyncio.sleep(0)
                color_temp = self._hex_to_rgb(hex_color, default_a)
                set_color.append(color_temp)
        elif color == "white":
            set_color = [white_info_color]
        elif color == "default":
            if section == "exp":
                set_color = [default_exp]
            elif section == "info":
                set_color = [default_info_color]
            elif section == "all":
                set_color = [default_exp, default_rep, default_badge, default_info_color]
            else:
                return
        elif self._is_hex(color):
            set_color = [self._hex_to_rgb(color, default_a)]
        else:
            await ctx.send("**Not a valid color. Use** `default`, `white`, **a valid hex code formatted like** `#990000`, **or** `auto` **for automatic**.")
            return

        if section == "all":
            if len(set_color) == 1:
                await self.db.users.update_one(
                    {"user_id": str(user.id)},
                    {"$set": {"rank_exp_color": set_color[0], "rank_info_color": set_color[0]}},
                )
            elif color == "default":
                await self.db.users.update_one(
                    {"user_id": str(user.id)},
                    {"$set": {"rank_exp_color": default_exp, "rank_info_color": default_info_color,}},
                )
            elif color == "auto":
                await self.db.users.update_one(
                    {"user_id": str(user.id)},
                    {"$set": {"rank_exp_color": set_color[0], "rank_info_color": set_color[1]}},
                )
            await ctx.send("**Colors for rank set.**")
        else:
            await self.db.users.update_one({"user_id": str(user.id)}, {"$set": {section_name: set_color[0]}})
            await ctx.send("**Color for rank {} set.**".format(section))

    @levelupset.command(name="color")
    @commands.guild_only()
    async def levelupcolors(self, ctx, section: str, color: str = None):
        """
        Set colors on your levelup message, if enabled.

        **section** can only be: `info`
        `info` is the backdrop of the text info areas

        **color** can be one of: `default` `white` `auto` or a hex code formatted like `#990000`
        `default` will reset levelup colors to the default colors
        `white` is used for a greyish transparent white, can be better than #FFFFFF
        `auto` automatically chooses the appropriate colors based on the levelup background image
        """
        user = ctx.author
        server = ctx.guild

        # the only color customizable section on a levelup message is the "info" area, maybe more in the future
        section = "info"
        
        # creates user if doesn't exist
        await self._create_user(user, server)
        userinfo = await self.db.users.find_one({"user_id": str(user.id)})

        section = section.lower()
        default_info_color = (30, 30, 30, 200)
        white_info_color = (150, 150, 150, 180)
        default_a = 200

        if await self.config.guild(ctx.guild).disabled():
            await ctx.send("**Leveler commands for this server are disabled!**")
            return

        if await self.config.guild(ctx.guild).text_only():
            await ctx.send("**Leveler is in text-only mode.**")
            return

        # get correct color choice
        if color == "auto":
            if section == "info":
                color_ranks = [random.randint(0, 1)]
            else:
                return
            hex_colors = await self._auto_color(ctx, userinfo["levelup_background"], color_ranks)
            set_color = []
            for hex_color in hex_colors:
                await asyncio.sleep(0)
                color_temp = self._hex_to_rgb(hex_color, default_a)
                set_color.append(color_temp)
        elif color == "white":
            set_color = [white_info_color]
        elif color == "default":
            if section == "info":
                set_color = [default_info_color]
            else:
                return
        elif self._is_hex(color):
            set_color = [self._hex_to_rgb(color, default_a)]
        else:
            await ctx.send("**Not a valid color. Use** `default`, `white`, **a valid hex code formatted like** `#990000`, **or** `auto` **for automatic**.")
            return

        await self.db.users.update_one({"user_id": str(user.id)}, {"$set": {section_name: set_color[0]}})
        await ctx.send("**Color for level-up {} set.**".format(section))

    # uses k-means algorithm to find color from bg, rank is abundance of color, descending
    async def _auto_color(self, ctx, url: str, ranks):
        phrases = ["Calculating colors...", "Reticulating Splines..."]  # in case I want more
        await ctx.send("**{}**".format(random.choice(phrases)))
        clusters = 10

        async with self.session.get(url) as r:
            image = await r.content.read()
        with open(f"{cog_data_path(self)}/temp_auto.png", "wb") as f:
            f.write(image)

        im = Image.open(f"{cog_data_path(self)}/temp_auto.png").convert("RGBA")
        im = im.resize((290, 290))  # resized to reduce time
        ar = numpy.asarray(im)
        shape = ar.shape
        ar = ar.reshape(scipy.product(shape[:2]), shape[2])

        codes, dist = scipy.cluster.vq.kmeans(ar.astype(float), clusters)
        vecs, dist = scipy.cluster.vq.vq(ar, codes)  # assign codes
        counts, bins = scipy.histogram(vecs, len(codes))  # count occurrences

        # sort counts
        freq_index = []
        index = 0
        for count in counts:
            await asyncio.sleep(0)
            freq_index.append((index, count))
            index += 1
        sorted_list = sorted(freq_index, key=operator.itemgetter(1), reverse=True)

        colors = []
        for rank in ranks:
            await asyncio.sleep(0)
            color_index = min(rank, len(codes))
            peak = codes[sorted_list[color_index][0]]  # gets the original index
            peak = peak.astype(int)

            colors.append("".join(format(c, "02x") for c in peak))
        return colors  # returns array

    # converts hex to rgb
    @staticmethod
    def _hex_to_rgb(hex_num: str, a: int):
        h = hex_num.lstrip("#")

        # if only 3 characters are given
        if len(str(h)) == 3:
            expand = "".join([x * 2 for x in str(h)])
            h = expand

        colors = [int(h[i : i + 2], 16) for i in (0, 2, 4)]
        colors.append(a)
        return tuple(colors)

    # dampens the color given a parameter
    @staticmethod
    def _moderate_color(rgb, a, moderate_num):
        new_colors = []
        for color in rgb[:3]:
            if color > 128:
                color -= moderate_num
            else:
                color += moderate_num
            new_colors.append(color)
        new_colors.append(230)

        return tuple(new_colors)

    @profileset.command()
    @commands.guild_only()
    async def info(self, ctx, *, info):
        """Set your user info."""
        user = ctx.author
        server = ctx.guild
        # creates user if doesn't exist
        await self._create_user(user, server)
        max_char = 150

        if await self.config.guild(ctx.guild).disabled():
            await ctx.send("**Leveler commands for this server are disabled.**")
            return

        if len(info) < max_char:
            await self.db.users.update_one({"user_id": str(user.id)}, {"$set": {"info": info}})
            await ctx.send("**Your info section has been successfully set!**")
        else:
            await ctx.send("**Your description has too many characters! Must be <{}**".format(max_char))

    @levelupset.command(name="bg")
    @commands.guild_only()
    async def levelbg(self, ctx, *, image_name: str):
        """Set your level background."""
        user = ctx.author
        server = ctx.guild
        backgrounds = await self.get_backgrounds()
        # creates user if doesn't exist
        await self._create_user(user, server)

        if await self.config.guild(ctx.guild).disabled():
            await ctx.send("**Leveler commands for this server are disabled.**")
            return

        if await self.config.guild(ctx.guild).text_only():
            await ctx.send("**Leveler is in text-only mode.**")
            return

        if image_name in backgrounds["levelup"].keys():
            if await self._process_purchase(ctx):
                await self.db.users.update_one(
                    {"user_id": str(user.id)}, {"$set": {"levelup_background": backgrounds["levelup"][image_name]}},
                )
                await ctx.send(
                    "**Your new level-up background has been successfully set!\nCalculate matching colors next by using** `{}lvlset levelup color info auto`".format(
                        ctx.prefix
                    )
                )
        else:
            await ctx.send(f"That is not a valid bg. See available bgs at `{ctx.prefix}backgrounds levelup`")

    @profileset.command(name="bg")
    @commands.guild_only()
    async def profilebg(self, ctx, *, image_name: str):
        """Set your profile background."""
        user = ctx.author
        server = ctx.guild
        backgrounds = await self.get_backgrounds()
        # creates user if doesn't exist
        await self._create_user(user, server)

        if await self.config.guild(ctx.guild).disabled():
            await ctx.send("**Leveler commands for this server are disabled.**")
            return

        if await self.config.guild(ctx.guild).text_only():
            await ctx.send("**Leveler is in text-only mode.**")
            return

        if image_name in backgrounds["profile"].keys():
            if await self._process_purchase(ctx):
                await self.db.users.update_one(
                    {"user_id": str(user.id)}, {"$set": {"profile_background": backgrounds["profile"][image_name]}},
                )
                await ctx.send(
                    "**Your new profile background has been successfully set!\nCalculate matching colors next by using** `{}lvlset profile color all auto`".format(
                        ctx.prefix
                    )
                )
        else:
            await ctx.send(f"That is not a valid bg. See available bgs at `{ctx.prefix}backgrounds profile`")

    @rankset.command(name="bg")
    @commands.guild_only()
    async def rankbg(self, ctx, *, image_name: str):
        """Set your rank background."""
        user = ctx.author
        server = ctx.guild
        backgrounds = await self.get_backgrounds()
        # creates user if doesn't exist
        await self._create_user(user, server)

        if await self.config.guild(ctx.guild).disabled():
            await ctx.send("**Leveler commands for this server are disabled.**")
            return

        if await self.config.guild(ctx.guild).text_only():
            await ctx.send("**Leveler is in text-only mode.**")
            return

        if image_name in backgrounds["rank"].keys():
            if await self._process_purchase(ctx):
                await self.db.users.update_one(
                    {"user_id": str(user.id)}, {"$set": {"rank_background": backgrounds["rank"][image_name]}},
                )
                await ctx.send(
                    "**Your new rank background has been successfully set!\nCalculate matching colors next by using** `{}lvlset rank color all auto`".format(
                        ctx.prefix
                    )
                )
        else:
            await ctx.send(f"That is not a valid bg. See available bgs at `{ctx.prefix}backgrounds rank`")

    @profileset.command()
    @commands.guild_only()
    async def title(self, ctx, *, title=None):
        """Set your title."""
        user = ctx.author
        server = ctx.guild
        # creates user if doesn't exist
        await self._create_user(user, server)
        max_char = 20

        if await self.config.guild(ctx.guild).disabled():
            await ctx.send("**Leveler commands for this server are disabled.**")
            return

        if title is None:
            await self.db.users.update_one({"user_id": str(user.id)}, {"$set": {"title": ""}})
            msg = "**Your title has been successfully cleared!**\n"
            msg += "Use this command with a title if you'd like to set one."
            await ctx.send(msg)
            return

        if len(title) < max_char:
            await self.db.users.update_one({"user_id": str(user.id)}, {"$set": {"title": title}})
            await ctx.send("**Your title has been successfully set!**")
        else:
            await ctx.send("**Your title has too many characters! Must be <{}**".format(max_char))

    @checks.admin_or_permissions(manage_guild=True)
    @commands.group()
    @commands.guild_only()
    async def lvladmin(self, ctx):
        """Admin settings."""
        pass

    @checks.mod_or_permissions(manage_messages=True)
    @commands.bot_has_permissions(embed_links=True)
    @lvladmin.group(invoke_without_command=True)
    async def overview(self, ctx, guild_id: int = None):
        """A list of settings."""
        num_users = await self.db.users.count_documents({})
        default_profile = await self.config.default_profile()
        default_rank = await self.config.default_rank()
        default_levelup = await self.config.default_levelup()

        if guild_id is not None:
            if ctx.author.id in self.bot.owner_ids:
                guild_data = await self.config.guild_from_id(guild_id).all()   
                g = self.bot.get_guild(guild_id)
            else:
                guild_data = await self.config.guild(ctx.guild).all()
                g = ctx.guild
        else:
            guild_data = await self.config.guild(ctx.guild).all()
            g = ctx.guild

        msg = "`Guild Settings`\n"
        msg += "**Leveler on {}:** {}\n".format(ctx.guild.name if not g else g.name, "Disabled" if guild_data['disabled'] else "Enabled")
        msg += "**Mentions on {}:** {}\n".format(ctx.guild.name if not g else g.name, "Enabled" if guild_data['mentions'] else "Disabled")
        msg += "**Public Level Messages:** {}\n".format("Enabled" if guild_data['lvl_msg'] else "Disabled")
        msg += "**Private Level Messages:** {}\n".format("Enabled" if guild_data['private_lvl_message'] else "Disabled")
        msg += "**Channel Locks:** {}\n".format(ctx.guild.get_channel(guild_data['lvl_msg_lock']))
 
        msg += "\n`Bot Owner Only Settings`\n"
        msg += "**Background Price:** {}\n".format(await self.config.bg_price())
        msg += "**Rep Reset Price:** {}\n".format(await self.config.rep_price())
        msg += "**Badge Type:** {}\n".format(await self.config.badge_type())
        msg += "**Default Profile Background:** {}\n".format(default_profile)
        msg += "**Default Rank Background:** {}\n".format(default_rank)
        msg += "**Default Levelup Background:** {}\n".format(default_levelup)

        if ctx.author.id in self.bot.owner_ids:
            msg += "\n**Servers:** {}\n".format(len(self.bot.guilds))
            msg += "**Unique Users:** {}\n".format(num_users)

        em = discord.Embed(description=msg, colour=await ctx.embed_color())
        em.set_author(name="Settings Overview for {}".format(g.name))
        await ctx.send(embed=em)

    @lvladmin.command()
    @checks.is_owner()
    @commands.check(non_global_bank)
    @commands.guild_only()
    async def msgcredits(self, ctx, currency: int = 0):
        """Credits per message logged. Default = 0"""
        channel = ctx.channel
        server = ctx.guild

        if currency < 0 or currency > 1000:
            await ctx.send("**Please enter a valid number (0 - 1000)**".format(channel.name))
            return

        await self.config.guild(server).msg_credits.set(currency)
        await ctx.send("**Credits per message logged set to `{}`.**".format(currency))

    @lvladmin.command()
    @commands.guild_only()
    async def ignorechannel(self, ctx, channel: discord.TextChannel = None):
        """Blocks exp gain in the given channel.

        Use command with no channel to see list of ignored channels."""
        server = ctx.guild
        if channel is None:
            channels = [
                server.get_channel(c) and server.get_channel(c).mention or c
                for c in await self.config.guild(server).ignored_channels()
                if server.get_channel(c)
            ]
            await ctx.send("**Ignored channels:** \n" + ("\n".join(channels) or "No ignored channels set."))
            return
        if channel.id in await self.config.guild(server).ignored_channels():
            async with self.config.guild(server).ignored_channels() as channels:
                channels.remove(channel.id)
            await ctx.send(f"**Messages in {channel.mention} will give exp now.**")
        else:
            async with self.config.guild(server).ignored_channels() as channels:
                channels.append(channel.id)
            await ctx.send(f"**Messages in {channel.mention} will not give exp now.**")

    @lvladmin.command(name="lock")
    @commands.guild_only()
    async def lvlmsglock(self, ctx, channel: discord.TextChannel = None):
        """Locks levelup messages to one channel. Use with no channel to disable."""
        server = ctx.guild

        if not channel:
            await self.config.guild(server).lvl_msg_lock.set(None)
            await ctx.send("**Level-up message lock disabled.**")
        else:
            await self.config.guild(server).lvl_msg_lock.set(channel.id)
            await ctx.send("**Level-up messages locked to `#{}`**".format(channel.name))

    async def _process_purchase(self, ctx):
        user = ctx.author
        # server = ctx.guild
        bg_price = await self.config.bg_price()
        if bg_price != 0:
            if not await bank.can_spend(user, bg_price):
                await ctx.send("**Insufficient funds. Backgrounds changes cost: ${}**".format(bg_price))
                return False
            else:
                await ctx.send(
                    "**{}, you are about to buy a background for `{}`. Confirm by typing** `yes`.".format(
                        await self._is_mention(user), bg_price
                    )
                )
                pred = MessagePredicate.yes_or_no(ctx)
                try:
                    await self.bot.wait_for("message", check=pred, timeout=15)
                except TimeoutError:
                    await ctx.send("**Purchase canceled.**")
                    return False
                if pred.result is True:
                    await bank.withdraw_credits(user, bg_price)
                    return True
                else:
                    await ctx.send("**Purchase canceled.**")
                    return False
        else:
            return True

    async def _give_chat_credit(self, user, server):
        msg_credits = await self.config.guild(server).msg_credits()
        if msg_credits and not await bank.is_global():
            await bank.deposit_credits(user, msg_credits)

    @checks.is_owner()
    @lvladmin.command()
    @commands.guild_only()
    async def setbgprice(self, ctx, price: int):
        """Set a price for background changes."""
        if price < 0:
            await ctx.send("**That is not a valid background price.**")
        else:
            await self.config.bg_price.set(price)
            await ctx.send(f"**Background price set to: `{price}`!**")

    @checks.is_owner()
    @lvladmin.command()
    @commands.guild_only()
    async def setrepprice(self, ctx, price: int):
        """Set a price for rep resets."""
        if price < 0:
            await ctx.send("**That is not a valid rep reset price.**")
        else:
            await self.config.rep_price.set(price)
            await ctx.send(f"**Rep reset price set to: `{price}`!**")

    @checks.is_owner()
    @lvladmin.command()
    @commands.guild_only()
    async def setlevel(self, ctx, user: discord.Member, level: int):
        """Set a user's level. (What a cheater C:)."""
        server = user.guild
        channel = ctx.channel
        # creates user if doesn't exist
        await self._create_user(user, server)
        userinfo = await self.db.users.find_one({"user_id": str(user.id)})

        if await self.config.guild(ctx.guild).disabled():
            await ctx.send("**Leveler commands for this server are disabled.**")
            return

        if level < 0:
            await ctx.send("**Please enter a positive number.**")
            return

        if level > 10000:
            await ctx.send("**Please enter a number that is less than 10,000.**")
            return

        # get rid of old level exp
        old_server_exp = 0
        for i in range(userinfo["servers"][str(server.id)]["level"]):
            await asyncio.sleep(0)
            old_server_exp += self._required_exp(i)
        userinfo["total_exp"] -= old_server_exp
        userinfo["total_exp"] -= userinfo["servers"][str(server.id)]["current_exp"]

        # add in new exp
        total_exp = self._level_exp(level)
        userinfo["servers"][str(server.id)]["current_exp"] = 0
        userinfo["servers"][str(server.id)]["level"] = level
        userinfo["total_exp"] += total_exp

        await self.db.users.update_one(
            {"user_id": str(user.id)},
            {
                "$set": {
                    "servers.{}.level".format(server.id): level,
                    "servers.{}.current_exp".format(server.id): 0,
                    "total_exp": userinfo["total_exp"],
                }
            },
        )
        await ctx.send("**{}'s Level has been set to `{}`.**".format(await self._is_mention(user), level))
        await self._handle_levelup(user, userinfo, server, channel)

    @checks.is_owner()
    @lvladmin.command()
    @commands.guild_only()
    async def setrep(self, ctx, user: discord.Member, rep_level: int):
        """Set a user's rep level. (What a cheater C:)."""
        server = user.guild
        channel = ctx.channel

        if rep_level < 0:
            await ctx.send("**Please enter a positive number.**")
            return
        if rep_level > 99999:
            await ctx.send("**Please use a number that is smaller than 100,000.**")
            return

        # creates user if doesn't exist
        await self._create_user(user, server)

        if await self.config.guild(ctx.guild).disabled():
            await ctx.send("**Leveler commands for this server are disabled.**")
            return

        await self.db.users.update_one({"user_id": str(user.id)}, {"$set": {"rep": rep_level}})

        await ctx.send("**{}'s rep has been set to `{}`.**".format(await self._is_mention(user), rep_level))

    @checks.is_owner()
    @lvladmin.command()
    @commands.guild_only()
    async def xpban(self, ctx, days: int, *, user: Union[discord.Member, int, None]):
        """Ban user from getting experience."""
        if isinstance(user, int):
            try:
                user = await self.bot.fetch_user(user)
            except (discord.HTTPException, discord.NotFound):
                user = None
        if user is None:
            await ctx.send_help()
            return
        chat_block = time.time() + timedelta(days=days).total_seconds()
        try:
            await self.db.users.update_one({"user_id": str(user.id)}, {"$set": {"chat_block": chat_block}})
        except Exception as exc:
            await ctx.send("Unable to add chat block: {}".format(exc))
        else:
            await ctx.tick()

    @checks.is_owner()
    @lvladmin.command()
    @commands.guild_only()
    async def mention(self, ctx):
        """Toggle mentions on messages."""
        if await self.config.guild(ctx.guild).mentions():
            await self.config.guild(ctx.guild).mentions.set(False)
            await ctx.send("**Mentions disabled.**")
        else:
            await self.config.guild(ctx.guild).mentions.set(True)
            await ctx.send("**Mentions enabled.**")

    async def _valid_image_url(self, url):
        try:
            async with self.session.get(url) as r:
                image = await r.read()
            return Image.open(BytesIO(image)).convert("RGBA")
        except Exception as exc:
            log.exception(
                "Something went wrong while trying to get a badge image or convert it: ", exc_info=exc,
            )
            return None

    @checks.admin_or_permissions(manage_guild=True)
    @lvladmin.command()
    @commands.guild_only()
    async def toggle(self, ctx):
        """Toggle most leveler commands on the current server."""
        server = ctx.guild
        if await self.config.guild(server).disabled():
            await self.config.guild(server).disabled.set(False)
            await ctx.send("**Leveler enabled on `{}`.**".format(server.name))
        else:
            await self.config.guild(server).disabled.set(True)
            await ctx.send("**Leveler disabled on `{}`.**".format(server.name))

    @checks.admin_or_permissions(manage_guild=True)
    @lvladmin.command()
    @commands.guild_only()
    async def textonly(self, ctx):
        """Toggle text-based messages on the server."""
        server = ctx.guild
        if await self.config.guild(server).text_only():
            await self.config.guild(server).text_only.set(False)
            await ctx.send("**Text-only messages disabled for `{}`.**".format(server.name))
        else:
            await self.config.guild(server).text_only.set(True)
            await ctx.send("**Text-only messages enabled for `{}`.**".format(server.name))

    @checks.admin_or_permissions(manage_guild=True)
    @lvladmin.command(name="alerts")
    @commands.guild_only()
    async def lvlalert(self, ctx):
        """Toggle level-up messages on the server."""
        server = ctx.guild
        # user = ctx.author

        if await self.config.guild(server).lvl_msg():
            await self.config.guild(server).lvl_msg.set(False)
            await ctx.send("**Level-up alerts disabled for `{}`.**".format(server.name))
        else:
            await self.config.guild(server).lvl_msg.set(True)
            await ctx.send("**Level-up alerts enabled for `{}`.**".format(server.name))

    @checks.admin_or_permissions(manage_guild=True)
    @lvladmin.command(name="private")
    @commands.guild_only()
    async def lvlprivate(self, ctx):
        """Toggles if level alert is a private message to the user."""
        server = ctx.guild
        if await self.config.guild(server).private_lvl_message():
            await self.config.guild(server).private_lvl_message.set(False)
            await ctx.send("**Private level-up alerts disabled for `{}`.**".format(server.name))
        else:
            await self.config.guild(server).private_lvl_message.set(True)
            await ctx.send("**Private level-up alerts enabled for `{}`.**".format(server.name))

    @lvladmin.command()
    @checks.is_owner()
    async def xp(self, ctx, min_xp: int = None, max_xp: int = None):
        """Set the range for the xp given on each successful xp gain.
        Leaving the entries blank will reset the xp to the default."""
        if not (min_xp and max_xp):
            await self.config.xp.set([15, 20])
            return await ctx.send("XP given has been reset to the default range of 15-20 xp per message.")
        elif not max_xp:
            return await ctx.send(f"Enter the values as a range: `{ctx.prefix}lvladmin xp 15 20`")
        elif (max_xp or min_xp) > 1000:
            return await ctx.send(
                "Don't you think that number is a bit high? That might break things. Try something under 1k xp."
            )
        elif min_xp >= max_xp:
            return await ctx.send("The minimum xp amount needs to be less than the maximum xp amount.")
        elif (min_xp or max_xp) <= 0:
            return await ctx.send("The xp amounts can't be zero or less.")
        else:
            await self.config.xp.set([min_xp, max_xp])
            await ctx.send(f"XP given has been set to a range of {min_xp} to {max_xp} xp per message.")

    @commands.group()
    @commands.guild_only()
    async def badges(self, ctx):
        """Badge configuration options."""
        pass

    @badges.command(name="available")
    @commands.bot_has_permissions(embed_links=True)
    @commands.guild_only()
    async def badge_available(self, ctx):
        """Get a list of available badges."""
        ids = [
            ("global", "Global", self.bot.user.avatar_url),
            (ctx.guild.id, ctx.guild.name, ctx.guild.icon_url),
        ]

        global_list = []
        server_list = []

        for serverid, servername, icon_url in ids:
            await asyncio.sleep(0)
            msg = ""
            server_badge_info = await self.db.badges.find_one({"server_id": str(serverid)})
            if server_badge_info:
                server_badges = server_badge_info["badges"]
                if len(server_badges) >= 1:
                    for badgename in server_badges:
                        await asyncio.sleep(0)
                        badgeinfo = server_badges[badgename]
                        if badgeinfo["price"] == -1:
                            price = "Non-purchasable"
                        elif badgeinfo["price"] == 0:
                            price = "Free"
                        else:
                            price = badgeinfo["price"]

                        msg += "**• {}** ({}) - {}\n".format(badgename, price, badgeinfo["description"])
                else:
                    msg = "None."
            else:
                msg = "None."

            total_pages = len(list(pagify(msg, ["\n"], page_length=1500)))
            page_num = 1
            for page in pagify(msg, ["\n"], page_length=1500):
                em = discord.Embed(colour=await ctx.embed_color(), description=page)
                em.set_author(name="{}".format(servername), icon_url=icon_url)
                em.set_footer(text="Page {} of {}".format(page_num, total_pages))
                page_num += 1
                if serverid == "global":
                    global_list.append(em)
                else:
                    server_list.append(em)

        for embed in global_list + server_list:
            await ctx.send(embed=embed)

    @badges.command(name="list")
    @commands.bot_has_permissions(embed_links=True)
    @commands.guild_only()
    async def listuserbadges(self, ctx, user: discord.Member = None):
        """
        List all of a user's badges.
        0 or -1 on the priority number means the badge is not visible on the profile.
		"""
        if user is None:
            user = ctx.author
        server = ctx.guild
        await self._create_user(user, server)
        userinfo = await self.db.users.find_one({"user_id": str(user.id)})
        userinfo = await self._badge_convert_dict(userinfo)

        # sort
        priority_badges = []
        for badgename in userinfo["badges"].keys():
            badge = userinfo["badges"][badgename]
            priority_num = badge["priority_num"]
            priority_badges.append((badge, priority_num))
        sorted_badges = sorted(priority_badges, key=operator.itemgetter(1), reverse=True)

        badge_ranks = ""
        counter = 1
        for badge, priority_num in sorted_badges:
            badge_ranks += "**{}. {}** ({}) [{}] **—** {}\n".format(
                counter, badge["badge_name"], badge["server_name"], priority_num, badge["description"],
            )
            counter += 1
        if not badge_ranks:
            badge_ranks = "None"

        total_pages = len(list(pagify(badge_ranks, ["\n"], page_length=1500)))
        embeds = []
        counter = 1
        for page in pagify(badge_ranks, ["\n"], page_length=1500):
            em = discord.Embed(colour=user.colour)
            em.description = page
            em.set_author(name="Badges for {}".format(user.name), icon_url=user.avatar_url)
            em.set_footer(text="Page {} of {}".format(counter, total_pages))
            embeds.append(em)
            counter += 1
        if len(embeds) == 1:
            await ctx.send(embed=embeds[0])
        else:
            await menu(ctx, embeds, DEFAULT_CONTROLS)

    @badges.command(name="buy")
    @commands.guild_only()
    async def badge_buy(self, ctx, name: str, global_badge: str = None):
        """
        Buy a badge.

        Use `-global` after the badge name to specify a global badge.
        """
        user = ctx.author
        server = ctx.guild
        if global_badge == "-global":
            serverid = "global"
        else:
            serverid = server.id
        await self._create_user(user, server)
        userinfo = await self.db.users.find_one({"user_id": str(user.id)})
        userinfo = await self._badge_convert_dict(userinfo)
        server_badge_info = await self.db.badges.find_one({"server_id": str(serverid)})

        if server_badge_info:
            server_badges = server_badge_info["badges"]
            if name in server_badges:

                if "{}_{}".format(name, str(serverid)) not in userinfo["badges"].keys():
                    badge_info = server_badges[name]
                    if badge_info["price"] == -1:
                        await ctx.send("**That badge is not purchasable.**".format(name))
                    elif badge_info["price"] == 0:
                        userinfo["badges"][f"{name}_{serverid}"] = server_badges[name]
                        await self.db.users.update_one(
                            {"user_id": userinfo["user_id"]}, {"$set": {"badges": userinfo["badges"]}},
                        )
                        await ctx.send("**`{}` has been obtained.**".format(name))
                    else:
                        await ctx.send(
                            '**{}, you are about to buy the `{}` badge for `{}`. Confirm by typing** `yes`'.format(
                                await self._is_mention(user), name, badge_info["price"]
                            )
                        )
                        pred = MessagePredicate.yes_or_no(ctx)
                        try:
                            await self.bot.wait_for("message", check=pred, timeout=15)
                        except TimeoutError:
                            return await ctx.send("**Purchase canceled.**")
                        if pred.result is False:
                            await ctx.send("**Purchase canceled.**")
                            return
                        else:
                            if badge_info["price"] <= await bank.get_balance(user):
                                await bank.withdraw_credits(user, badge_info["price"])
                                userinfo["badges"]["{}_{}".format(name, str(serverid))] = server_badges[name]
                                await self.db.users.update_one(
                                    {"user_id": userinfo["user_id"]}, {"$set": {"badges": userinfo["badges"]}},
                                )
                                await ctx.send(
                                    "**You have bought the `{}` badge for `{}`.\nSet it on your profile by using** `{}badge set` **next.**".format(
                                        name, badge_info["price"], ctx.prefix
                                    )
                                )
                            elif await bank.get_balance(user) < badge_info["price"]:
                                await ctx.send(
                                    "**Not enough money! Need `{}` more.**".format(
                                        badge_info["price"] - await bank.get_balance(user)
                                    )
                                )
                else:
                    await ctx.send("**{}, you already have this badge!**".format(user.name))
            else:
                await ctx.send("**The badge `{}` does not exist. List badges with** `{}badge available`.".format(name, ctx.prefix))
        else:
            await ctx.send("**The badge `{}` does not exist in the global badge list. List badges with** `{}badge available`.".format(ctx.prefix))

    @badges.command(name="set")
    @commands.guild_only()
    async def badge_set(self, ctx, name: str, priority_num: int):
        """
        Set a badge on the profile. 

        `priority_num` is a priority number based on:
        `-1`\t\t: Invisible on profile card
        `0`\t\t: Not on profile card
        `1 - 5000`\t\t: Priority level. `1` is the least priority (last on badge display), `5000` is first.
        """
        user = ctx.author
        server = ctx.guild
        await self._create_user(user, server)

        userinfo = await self.db.users.find_one({"user_id": str(user.id)})
        userinfo = await self._badge_convert_dict(userinfo)

        if priority_num < -1 or priority_num > 5000:
            await ctx.send("**Invalid priority number! -1 to 5000.**")
            return

        for badge in userinfo["badges"]:
            await asyncio.sleep(0)
            if userinfo["badges"][badge]["badge_name"] == name:
                userinfo["badges"][badge]["priority_num"] = priority_num
                await self.db.users.update_one(
                    {"user_id": userinfo["user_id"]}, {"$set": {"badges": userinfo["badges"]}}
                )
                await ctx.send(
                    "**The `{}` badge priority has been set to `{}`!**".format(
                        userinfo["badges"][badge]["badge_name"], priority_num
                    )
                )
                break
        else:
            await ctx.send("**You don't have that badge!**")

    async def _badge_convert_dict(self, userinfo):
        if "badges" not in userinfo or not isinstance(userinfo["badges"], dict):
            await self.db.users.update_one({"user_id": userinfo["user_id"]}, {"$set": {"badges": {}}})
        return await self.db.users.find_one({"user_id": userinfo["user_id"]})

    @checks.mod_or_permissions(manage_roles=True)
    @badges.command(name="add")
    @commands.guild_only()
    async def badge_add(self, ctx, name: str, badge_image_url: str, border_color: str, price: int, *, description: str):
        """
        Add a badge.

        `name`: The name for your badge. Use one word.
        `badge_image_url`: The image url for the badge. Make sure it is on a permanent hosting service like imgur or similar.
        `border_color`: A hex code for color, formatted like `#990000`.
        `price`:
            `-1` Non-purchaseable.
            `0`  Free.
                 Otherwise it will be the number provided for price.
        `description`: A description for the badge. 

        Use `-global` after your description to make the badge global, if you are the bot owner.
        """

        user = ctx.author
        server = ctx.guild

        required_members = 25
        members = len([member for member in server.members if not member.bot])

        if members < required_members:
            await ctx.send("**You may only add badges in servers with {}+ non-bot members.**".format(required_members))
            return

        if "-global" in description and user.id in self.bot.owner_ids:
            description = description.replace(" -global", "")
            serverid = "global"
            servername = "global"
        else:
            serverid = server.id
            servername = server.name

        if "." in name:
            await ctx.send("**Name cannot contain `.`**")
            return

        if not await self._valid_image_url(badge_image_url):
            await ctx.send("**Background is not valid. Enter hex or image url!**")
            return

        if not self._is_hex(border_color):
            await ctx.send("**Border color is not valid!**")
            return

        if price < -1:
            await ctx.send("**Price is not valid!**")
            return

        if price > 9223372036854775807:
            # max economy balance
            await ctx.send("**Price needs to be lower!**")
            return

        if len(description.split(" ")) > 40:
            await ctx.send("**Description is too long! <=40**")
            return

        badges = await self.db.badges.find_one({"server_id": str(serverid)})
        if not badges:
            await self.db.badges.insert_one({"server_id": str(serverid), "badges": {}})
            badges = await self.db.badges.find_one({"server_id": str(serverid)})

        new_badge = {
            "badge_name": name,
            "bg_img": badge_image_url,
            "price": price,
            "description": description,
            "border_color": border_color,
            "server_id": str(serverid),
            "server_name": servername,
            "priority_num": 0,
        }

        if name not in badges["badges"].keys():
            # create the badge regardless
            badges["badges"][name] = new_badge
            await self.db.badges.update_one({"server_id": str(serverid)}, {"$set": {"badges": badges["badges"]}})
            await ctx.send("**`{}` badge added in `{}` server.**".format(name, servername))
        else:
            # update badge in the server
            badges["badges"][name] = new_badge
            await self.db.badges.update_one({"server_id": serverid}, {"$set": {"badges": badges["badges"]}})

            # go though all users and update the badge.
            # Doing it this way because dynamic does more accesses when doing profile
            async for user in self.db.users.find({}):
                await asyncio.sleep(0)
                try:
                    user = await self._badge_convert_dict(user)
                    userbadges = user["badges"]
                    badge_name = "{}_{}".format(name, serverid)
                    if badge_name in userbadges.keys():
                        user_priority_num = userbadges[badge_name]["priority_num"]
                        new_badge["priority_num"] = user_priority_num  # maintain old priority number set by user
                        userbadges[badge_name] = new_badge
                        await self.db.users.update_one({"user_id": user["user_id"]}, {"$set": {"badges": userbadges}})
                except:
                    pass
            await ctx.send("**The `{}` badge has been updated.**".format(name))

    @checks.is_owner()
    @badges.command(name="type")
    @commands.guild_only()
    async def badge_type(self, ctx, name: str):
        """Circles or bars."""
        valid_types = ["circles", "bars"]
        if name.lower() not in valid_types:
            await ctx.send("**That is not a valid badge type!**")
            return

        await self.config.badge_type.set(name.lower())
        await ctx.send("**Badge type set to `{}`.**".format(name.lower()))

    @checks.mod_or_permissions(manage_roles=True)
    @badges.command(name="delete", aliases=["remove"])
    @commands.guild_only()
    async def badge_delete(self, ctx, *, name: str):
        """
        Delete a badge.

        Use `-global` after the badge name to specify a global badge.
        """
        user = ctx.author
        server = ctx.guild

        if "-global" in name and user.id in self.bot.owner_ids:
            name = name.replace(" -global", "")
            serverid = "global"
        else:
            serverid = server.id

        # creates user if doesn't exist
        await self._create_user(user, server)

        if await self.config.guild(server).disabled():
            await ctx.send("**Leveler commands for this server are disabled.**")
            return

        serverbadges = await self.db.badges.find_one({"server_id": str(serverid)})
        if name in serverbadges["badges"].keys():
            del serverbadges["badges"][name]
            await self.db.badges.update_one(
                {"server_id": serverbadges["server_id"]}, {"$set": {"badges": serverbadges["badges"]}},
            )
            # remove the badge if there
            async for user_info_temp in self.db.users.find({}):
                try:
                    user_info_temp = await self._badge_convert_dict(user_info_temp)

                    badge_name = "{}_{}".format(name, serverid)
                    if badge_name in user_info_temp["badges"].keys():
                        del user_info_temp["badges"][badge_name]
                        await self.db.users.update_one(
                            {"user_id": user_info_temp["user_id"]}, {"$set": {"badges": user_info_temp["badges"]}},
                        )
                except Exception as exc:
                    log.error(f"Unable to delete badge {name} from {user_info_temp['user_id']}: {exc}")

            await ctx.send("**The `{}` badge has been removed.**".format(name))
        else:
            await ctx.send("**That badge does not exist.**")

    @checks.mod_or_permissions(manage_roles=True)
    @badges.command(name="give")
    @commands.guild_only()
    async def badge_give(self, ctx, user: discord.Member, name: str, global_badge: str = None):
        """
        Give a user a badge. 
        
        Use `-global` after the badge name to specify a global badge.
        """
        org_user = ctx.message.author
        server = ctx.guild

        # creates user if doesn't exist
        await self._create_user(user, server)
        userinfo = await self.db.users.find_one({"user_id": str(user.id)})
        userinfo = await self._badge_convert_dict(userinfo)

        if await self.config.guild(server).disabled():
            await ctx.send("**Leveler commands for this server are disabled.**")
            return

        if global_badge == "-global":
            badgeserver = "global"
        else:
            badgeserver = ctx.guild.id
        serverbadges = await self.db.badges.find_one({"server_id": str(badgeserver)})
        if serverbadges:
            badges = serverbadges["badges"]
        else:
            badges = None
        badge_name = "{}_{}".format(name, server.id)

        if not badges:
            await ctx.send("**That badge doesn't exist in this server!**")
            return
        elif badge_name in badges.keys():
            await ctx.send("**{} already has that badge!**".format(await self._is_mention(user)))
            return
        else:
            try:
                userinfo["badges"][badge_name] = badges[name]
                await self.db.users.update_one({"user_id": str(user.id)}, {"$set": {"badges": userinfo["badges"]}})
                await ctx.send(
                    "**{} has just given {} the `{}` badge!**".format(
                        await self._is_mention(org_user), await self._is_mention(user), name
                    )
                )
            except KeyError:
                await ctx.send("**That badge doesn't exist in this server!**")

    @checks.mod_or_permissions(manage_roles=True)
    @badges.command(name="take")
    @commands.guild_only()
    async def badge_take(self, ctx, user: discord.Member, name: str):
        """Take a user's badge."""
        org_user = ctx.author
        server = ctx.guild
        # creates user if doesn't exist
        await self._create_user(user, server)
        userinfo = await self.db.users.find_one({"user_id": str(user.id)})
        userinfo = await self._badge_convert_dict(userinfo)

        if await self.config.guild(server).disabled():
            await ctx.send("**Leveler commands for this server are disabled.**")
            return

        serverbadges = await self.db.badges.find_one({"server_id": str(server.id)})
        badges = serverbadges["badges"]
        badge_name = "{}_{}".format(name, server.id)

        if name not in badges:
            await ctx.send("**That badge doesn't exist in this server!**")
        elif badge_name not in userinfo["badges"]:
            await ctx.send("**{} does not have that badge!**".format(await self._is_mention(user)))
        else:
            del userinfo["badges"][badge_name]
            await self.db.users.update_one({"user_id": str(user.id)}, {"$set": {"badges": userinfo["badges"]}})
            await ctx.send(
                "**{} has taken the `{}` badge from {}! :upside_down:**".format(
                    await self._is_mention(org_user), name, await self._is_mention(user)
                )
            )

    @checks.mod_or_permissions(manage_roles=True)
    @badges.command(name="link")
    @commands.guild_only()
    async def badge_link(self, ctx, badge_name: str, level: int):
        """Associate a badge with a level."""
        server = ctx.guild
        serverbadges = await self.db.badges.find_one({"server_id": str(server.id)})

        if serverbadges is None:
            await ctx.send("**This server does not have any badges!**")
            return

        if badge_name not in serverbadges["badges"].keys():
            await ctx.send("**Please make sure the `{}` badge exists!**".format(badge_name))
            return
        else:
            server_linked_badges = await self.db.badgelinks.find_one({"server_id": str(server.id)})
            if not server_linked_badges:
                new_server = {"server_id": str(server.id), "badges": {badge_name: str(level)}}
                await self.db.badgelinks.insert_one(new_server)
            else:
                server_linked_badges["badges"][badge_name] = str(level)
                await self.db.badgelinks.update_one(
                    {"server_id": str(server.id)}, {"$set": {"badges": server_linked_badges["badges"]}},
                )
            await ctx.send("**The `{}` badge has been linked to level `{}`.**".format(badge_name, level))

    @checks.admin_or_permissions(manage_roles=True)
    @badges.command(name="unlink")
    @commands.guild_only()
    async def badge_unlink(self, ctx, *, badge_name: str):
        """Unlink a badge/level association."""
        server = ctx.guild

        server_linked_badges = await self.db.badgelinks.find_one({"server_id": str(server.id)})
        badge_links = server_linked_badges["badges"]

        if badge_name in badge_links.keys():
            await ctx.send("**Badge/Level association `{}`/`{}` removed.**".format(badge_name, badge_links[badge_name]))
            del badge_links[badge_name]
            await self.db.badgelinks.update_one({"server_id": str(server.id)}, {"$set": {"badges": badge_links}})
        else:
            await ctx.send("**The `{}` badge is not linked to any levels!**".format(badge_name))

    @checks.mod_or_permissions(manage_roles=True)
    @badges.command(name="listlinks")
    @commands.bot_has_permissions(embed_links=True)
    @commands.guild_only()
    async def badge_list(self, ctx):
        """List badge/level associations."""
        server = ctx.guild

        server_badges = await self.db.badgelinks.find_one({"server_id": str(server.id)})

        em = discord.Embed(colour=await ctx.embed_color())
        em.set_author(name="Current Badge - Level Links for {}".format(server.name), icon_url=server.icon_url)

        if server_badges is None or "badges" not in server_badges or server_badges["badges"] == {}:
            msg = "None"
        else:
            badges = server_badges["badges"]
            msg = "**Badge** → Level\n"
            for badge in badges.keys():
                await asyncio.sleep(0)
                msg += "**• {} →** {}\n".format(badge, badges[badge])

        em.description = msg
        await ctx.send(embed=em)

    @commands.group()
    @commands.guild_only()
    @checks.mod_or_permissions(manage_roles=True)
    async def role(self, ctx):
        """Role configuration."""
        pass

    @role.command(name="link")
    @commands.guild_only()
    async def linkrole(self, ctx, role_name: str, level: int, remove_role=None):
        """Associate a role with a level. Removes previous role if given."""
        server = ctx.guild

        role_obj = discord.utils.find(lambda r: r.name == role_name, server.roles)
        remove_role_obj = discord.utils.find(lambda r: r.name == remove_role, server.roles)
        if role_obj is None or (remove_role is not None and remove_role_obj is None):
            if remove_role is None:
                await ctx.send("**Please make sure the `{}` role exists!**".format(role_name))
            else:
                await ctx.send("**Please make sure the `{}` and/or `{}` roles exist!**".format(role_name, remove_role))
        else:
            server_roles = await self.db.roles.find_one({"server_id": str(server.id)})
            if not server_roles:
                new_server = {
                    "server_id": str(server.id),
                    "roles": {role_name: {"level": str(level), "remove_role": remove_role}},
                }
                await self.db.roles.insert_one(new_server)
            else:
                if role_name not in server_roles["roles"]:
                    server_roles["roles"][role_name] = {}

                server_roles["roles"][role_name]["level"] = str(level)
                server_roles["roles"][role_name]["remove_role"] = remove_role
                await self.db.roles.update_one(
                    {"server_id": str(server.id)}, {"$set": {"roles": server_roles["roles"]}}
                )

            if remove_role is None:
                await ctx.send("**The `{}` role has been linked to level `{}`**".format(role_name, level))
            else:
                await ctx.send(
                    "**The `{}` role has been linked to level `{}`. "
                    "Will also remove `{}` role.**".format(role_name, level, remove_role)
                )

    @role.command(name="unlink")
    @commands.guild_only()
    async def unlinkrole(self, ctx, *, role_name: str):
        """Unlink a role/level association."""
        server = ctx.guild

        server_roles = await self.db.roles.find_one({"server_id": str(server.id)})
        roles = server_roles["roles"]

        if role_name in roles:
            await ctx.send("**Role/Level association `{}`/`{}` removed.**".format(role_name, roles[role_name]["level"]))
            del roles[role_name]
            await self.db.roles.update_one({"server_id": str(server.id)}, {"$set": {"roles": roles}})
        else:
            await ctx.send("**The `{}` role is not linked to any levels!**".format(role_name))

    @role.command(name="listlinks")
    @commands.bot_has_permissions(embed_links=True)
    @commands.guild_only()
    async def listrole(self, ctx):
        """List role/level associations."""
        server = ctx.guild
        # user = ctx.author

        server_roles = await self.db.roles.find_one({"server_id": str(server.id)})

        em = discord.Embed(colour=await ctx.embed_color())
        em.set_author(name="Current Role - Level Links for {}".format(server.name), icon_url=server.icon_url)

        if server_roles is None or "roles" not in server_roles or server_roles["roles"] == {}:
            msg = "None"
        else:
            roles = server_roles["roles"]
            msg = "**Role** → Level\n"
            for role in roles:
                await asyncio.sleep(0)
                if roles[role]["remove_role"] is not None:
                    msg += "**• {} →** {} (Removes: {})\n".format(
                        role, roles[role]["level"], roles[role]["remove_role"]
                    )
                else:
                    msg += "**• {} →** {}\n".format(role, roles[role]["level"])

        em.description = msg
        await ctx.send(embed=em)

    @lvladmin.group(name="bg")
    async def lvladminbg(self, ctx):
        """Background configuration."""
        pass

    @checks.is_owner()
    @lvladminbg.command()
    @commands.guild_only()
    async def addprofilebg(self, ctx, name: str, url: str):
        """Add a profile background. Proportions: (290px x 290px)"""
        backgrounds = await self.get_backgrounds()
        if name in backgrounds["profile"].keys():
            await ctx.send("**That profile background name already exists!**")
        elif not await self._valid_image_url(url):
            await ctx.send("**That is not a valid image url!**")
        else:
            async with self.config.backgrounds() as backgrounds:
                backgrounds["profile"][name] = url
            await ctx.send("**New profile background (`{}`) added.**".format(name))

    @checks.is_owner()
    @lvladminbg.command()
    @commands.guild_only()
    async def addrankbg(self, ctx, name: str, url: str):
        """Add a rank background. Proportions: (360px x 100px)"""
        backgrounds = await self.get_backgrounds()
        if name in backgrounds["profile"].keys():
            await ctx.send("**That rank background name already exists!**")
        elif not await self._valid_image_url(url):
            await ctx.send("**That is not a valid image url!**")
        else:
            async with self.config.backgrounds() as backgrounds:
                backgrounds["rank"][name] = url
            await ctx.send("**New rank background (`{}`) added.**".format(name))

    @checks.is_owner()
    @lvladminbg.command()
    @commands.guild_only()
    async def addlevelbg(self, ctx, name: str, url: str):
        """Add a level-up background. Proportions: (175px x 65px)"""
        backgrounds = await self.get_backgrounds()
        if name in backgrounds["levelup"].keys():
            await ctx.send("**That level-up background name already exists!**")
        elif not await self._valid_image_url(url):
            await ctx.send("**That is not a valid image url!**")
        else:
            async with self.config.backgrounds() as backgrounds:
                backgrounds["levelup"][name] = url
            await ctx.send("**New level-up background (`{}`) added.**".format(name))

    @checks.is_owner()
    @lvladminbg.command()
    @commands.guild_only()
    async def setcustombg(self, ctx, bg_type: str, user_id: str, img_url: str):
        """Set one-time custom profile background"""
        valid_types = ["profile", "rank", "levelup"]
        type_input = bg_type.lower()

        if type_input not in valid_types:
            await ctx.send("**Please choose a valid type: `profile`, `rank`, `levelup`.")
            return

        # test if valid user_id
        userinfo = await self.db.users.find_one({"user_id": str(user_id)})
        if not userinfo:
            await ctx.send("**That is not a valid user id!**")
            return

        if not await self._valid_image_url(img_url):
            await ctx.send("**That is not a valid image url!**")
            return

        await self.db.users.update_one(
            {"user_id": str(user_id)}, {"$set": {"{}_background".format(type_input): img_url}}
        )
        await ctx.send("**User {} custom {} background set.**".format(user_id, bg_type))

    @checks.is_owner()
    @lvladminbg.command()
    @commands.guild_only()
    async def defaultprofilebg(self, ctx, name: str):
        """Set a profile background as the new default profile background for new users.
        The profile bg must be in the existing profile background list.
        Does not convert existing users to the new default."""
        bgs = await self.get_backgrounds()
        if name in bgs["profile"].keys():
            await self.config.default_profile.set(bgs["profile"][name])
            return await ctx.send("**The profile background (`{}`) has been set as the new default.**".format(name))
        else:
            return await ctx.send("**That profile background name doesn't exist.**")

    @checks.is_owner()
    @lvladminbg.command()
    @commands.guild_only()
    async def defaultrankbg(self, ctx, name: str):
        """Set a rank background as the new default rank background for new users.
        The rank bg must be in the existing rank background list.
        Does not convert existing users to the new default."""
        bgs = await self.get_backgrounds()
        if name in bgs["rank"].keys():
            await self.config.default_rank.set(bgs["rank"][name])
            return await ctx.send("**The rank background (`{}`) has been set as the new default.**".format(name))
        else:
            return await ctx.send("**That rank background name doesn't exist.**")

    @checks.is_owner()
    @lvladminbg.command()
    @commands.guild_only()
    async def defaultlevelbg(self, ctx, name: str):
        """Set a levelup background as the new default levelup background for new users.
        The levelup bg must be in the existing levelup background list.
        Does not convert existing users to the new default."""
        bgs = await self.get_backgrounds()
        if name in bgs["levelup"].keys():
            await self.config.default_levelup.set(bgs["levelup"][name])
            return await ctx.send("**The levelup background (`{}`) has been set as the new default.**".format(name))
        else:
            return await ctx.send("**That levelup background name doesn't exist.**")

    @checks.is_owner()
    @lvladminbg.command()
    @commands.guild_only()
    async def delprofilebg(self, ctx, name: str):
        """Delete a profile background."""
        backgrounds = await self.get_backgrounds()
        if len(backgrounds["profile"]) == 1:
            return await ctx.send(
                "**Add more profile backgrounds with** `{}lvladmin bg addprofilebg` **before removing the last one!**".format(
                    ctx.prefix
                )
            )
        default_profile = await self.config.default_profile()
        try:
            if backgrounds["profile"][name] == default_profile:
                msg = (
                    "**That profile background is currently set as the default.**\n"
                    "Use `{}lvladmin bg defaultprofilebg` to set a new default profile background.\n"
                    "Then run `{}lvladmin bg delprofilebg {}` again once you have set the new default."
                ).format(ctx.prefix, ctx.prefix, name)
                return await ctx.send(msg)
            else:
                await self.delete_background("profile", name)
        except KeyError:
            return await ctx.send("**That profile background name doesn't exist.**")
        else:
            return await ctx.send("**The profile background (`{}`) has been deleted.**".format(name))

    @checks.is_owner()
    @lvladminbg.command()
    @commands.guild_only()
    async def delrankbg(self, ctx, name: str):
        """Delete a rank background."""
        backgrounds = await self.get_backgrounds()
        if len(backgrounds["rank"]) == 1:
            return await ctx.send(
                "**Add more rank backgrounds with** `{}lvladmin bg addrankbg` **before removing the last one!**".format(
                    ctx.prefix
                )
            )
        default_rank = await self.config.default_rank()
        try:
            if backgrounds["rank"][name] == default_rank:
                msg = (
                    "**That rank background is currently set as the default.**\n"
                    "Use `{}lvladmin bg defaultrankbg` to set a new default rank background.\n"
                    "Then run `{}lvladmin bg delrankbg {}` again once you have set the new default."
                ).format(ctx.prefix, ctx.prefix, name)
                return await ctx.send(msg)
            else:
                await self.delete_background("rank", name)
        except KeyError:
            return await ctx.send("**That profile background name doesn't exist.**")
        else:
            return await ctx.send("**The profile background (`{}`) has been deleted.**".format(name))

    @checks.is_owner()
    @lvladminbg.command()
    @commands.guild_only()
    async def dellevelbg(self, ctx, name: str):
        """Delete a level background."""
        backgrounds = await self.get_backgrounds()
        if len(backgrounds["levelup"]) == 1:
            return await ctx.send(
                "**Add more level up backgrounds with** `{}lvladmin bg addlevelbg` **before removing the last one!**".format(
                    ctx.prefix
                )
            )
        default_levelup = await self.config.default_levelup()
        try:
            if backgrounds["levelup"][name] == default_levelup:
                msg = (
                    "**That levelup background is currently set as the default.**\n"
                    "Use `{}lvladmin bg defaultlevelbg` to set a new default levelup background.\n"
                    "Then run `{}lvladmin bg dellevelbg {}` again once you have set the new default."
                ).format(ctx.prefix, ctx.prefix, name)
                return await ctx.send(msg)
            else:
                await self.delete_background("levelup", name)
        except KeyError:
            return await ctx.send("**That profile background name doesn't exist.**")
        else:
            return await ctx.send("**The profile background (`{}`) has been deleted.**".format(name))

    @commands.command(name="backgrounds")
    @commands.bot_has_permissions(embed_links=True)
    @commands.guild_only()
    async def disp_backgrounds(self, ctx, background_type):
        """
        Displays available backgrounds. 

        Valid background types are: `profile`, `rank`, or `levelup`.
        """
        server = ctx.guild
        backgrounds = await self.get_backgrounds()

        if await self.config.guild(server).disabled():
            await ctx.send("**Leveler commands for this server are disabled!**")
            return

        em = discord.Embed(colour=await ctx.embed_color())
        if background_type.lower() == "profile":
            em.set_author(
                name="Profile Backgrounds for {}".format(self.bot.user.name), icon_url=self.bot.user.avatar_url,
            )
            bg_key = "profile"
        elif background_type.lower() == "rank":
            em.set_author(
                name="Rank Backgrounds for {}".format(self.bot.user.name), icon_url=self.bot.user.avatar_url,
            )
            bg_key = "rank"
        elif background_type.lower() == "levelup":
            em.set_author(
                name="Level Up Backgrounds for {}".format(self.bot.user.name), icon_url=self.bot.user.avatar_url,
            )
            bg_key = "levelup"
        else:
            bg_key = None

        if bg_key:
            embeds = []
            total = len(backgrounds[bg_key])
            cnt = 1
            for bg in sorted(backgrounds[bg_key].keys()):
                await asyncio.sleep(0)
                em = discord.Embed(
                    title=bg,
                    color=await ctx.embed_color(),
                    url=backgrounds[bg_key][bg],
                    description=f"Background {cnt}/{total}",
                )
                em.set_image(url=backgrounds[bg_key][bg])
                embeds.append(em)
                cnt += 1
            await menu(ctx, embeds, DEFAULT_CONTROLS)
        else:
            await ctx.send("**Invalid Background Type. (profile, rank, levelup)**")

    async def draw_profile(self, user, server):
        if not self._db_ready:
            return
        font_file = f"{bundled_data_path(self)}/font.ttf"
        font_bold_file = f"{bundled_data_path(self)}/font_bold.ttf"
        font_unicode_file = f"{bundled_data_path(self)}/unicode.ttf"
        # name_fnt = ImageFont.truetype(font_bold_file, 22, encoding="utf-8")
        header_u_fnt = ImageFont.truetype(font_unicode_file, 18, encoding="utf-8")
        # title_fnt = ImageFont.truetype(font_file, 18, encoding="utf-8")
        sub_header_fnt = ImageFont.truetype(font_bold_file, 14, encoding="utf-8")
        # badge_fnt = ImageFont.truetype(font_bold_file, 10, encoding="utf-8")
        exp_fnt = ImageFont.truetype(font_bold_file, 14, encoding="utf-8")
        # large_fnt = ImageFont.truetype(font_bold_file, 33, encoding="utf-8")
        level_label_fnt = ImageFont.truetype(font_bold_file, 22, encoding="utf-8")
        general_info_fnt = ImageFont.truetype(font_bold_file, 15, encoding="utf-8")
        general_info_u_fnt = ImageFont.truetype(font_unicode_file, 12, encoding="utf-8")
        rep_fnt = ImageFont.truetype(font_bold_file, 26, encoding="utf-8")
        text_fnt = ImageFont.truetype(font_bold_file, 12, encoding="utf-8")
        text_u_fnt = ImageFont.truetype(font_unicode_file, 8, encoding="utf-8")
        # credit_fnt = ImageFont.truetype(font_bold_file, 10, encoding="utf-8")

        def _write_unicode(text, init_x, y, font, unicode_font, fill):
            write_pos = init_x

            for char in text:
                if char.isalnum() or char in string.punctuation or char in string.whitespace:
                    draw.text((write_pos, y), "{}".format(char), font=font, fill=fill)
                    write_pos += font.getsize(char)[0]
                else:
                    draw.text((write_pos, y), "{}".format(char), font=unicode_font, fill=fill)
                    write_pos += unicode_font.getsize(char)[0]

        # get urls
        userinfo = await self.db.users.find_one({"user_id": str(user.id)})
        await self._badge_convert_dict(userinfo)
        bg_url = userinfo["profile_background"]
        # profile_url = user.avatar_url

        # create image objects
        # bg_image = Image
        # profile_image = Image

        async with self.session.get(bg_url) as r:
            image = await r.content.read()
        profile_background = BytesIO(image)
        profile_avatar = BytesIO()
        try:
            await user.avatar_url.save(profile_avatar, seek_begin=True)
        except discord.HTTPException:
            profile_avatar = f"{bundled_data_path(self)}/defaultavatar.png"

        bg_image = Image.open(profile_background).convert("RGBA")
        profile_image = Image.open(profile_avatar).convert("RGBA")

        # set canvas
        bg_color = (255, 255, 255, 0)
        result = Image.new("RGBA", (290, 290), bg_color)
        process = Image.new("RGBA", (290, 290), bg_color)

        # draw
        draw = ImageDraw.Draw(process)

        # puts in background
        bg_image = bg_image.resize((290, 290), Image.ANTIALIAS)
        bg_image = bg_image.crop((0, 0, 290, 290))
        result.paste(bg_image, (0, 0))

        # draw filter
        draw.rectangle([(0, 0), (290, 290)], fill=(0, 0, 0, 10))

        # draw transparent overlay
        vert_pos = 110
        left_pos = 70
        right_pos = 285
        title_height = 22
        # gap = 3

        # determines rep section color
        if "rep_color" not in userinfo.keys() or not userinfo["rep_color"]:
            rep_fill = (92, 130, 203, 230)
        else:
            rep_fill = tuple(userinfo["rep_color"])
        # determines badge section color, should be behind the titlebar
        if "badge_col_color" not in userinfo.keys() or not userinfo["badge_col_color"]:
            badge_fill = (128, 151, 165, 230)
        else:
            badge_fill = tuple(userinfo["badge_col_color"])

        if "profile_info_color" in userinfo.keys():
            info_color = tuple(userinfo["profile_info_color"])
        else:
            info_color = (30, 30, 30, 220)

        draw.rectangle([(left_pos - 20, vert_pos + title_height), (right_pos, 156)], fill=info_color)  # title box
        draw.rectangle([(100, 159), (285, 212)], fill=info_color)  # general content
        draw.rectangle([(100, 215), (285, 285)], fill=info_color)  # info content

        # stick in credits if needed
        # if bg_url in bg_credits.keys():
        # credit_text = "  ".join("Background by {}".format(bg_credits[bg_url]))
        # credit_init = 290 - credit_fnt.getsize(credit_text)[0]
        # draw.text((credit_init, 0), credit_text,  font=credit_fnt, fill=(0,0,0,100))
        draw.rectangle(
            [(5, vert_pos), (right_pos, vert_pos + title_height)], fill=(230, 230, 230, 230)
        )  # name box in front

        # draw level circle
        multiplier = 8
        lvl_circle_dia = 104
        circle_left = 1
        circle_top = 42
        raw_length = lvl_circle_dia * multiplier

        # create mask
        mask = Image.new("L", (raw_length, raw_length), 0)
        draw_thumb = ImageDraw.Draw(mask)
        draw_thumb.ellipse((0, 0) + (raw_length, raw_length), fill=255, outline=0)

        # drawing level bar calculate angle
        start_angle = -90  # from top instead of 3oclock
        angle = (
            int(
                360
                * (
                    userinfo["servers"][str(server.id)]["current_exp"]
                    / self._required_exp(userinfo["servers"][str(server.id)]["level"])
                )
            )
            + start_angle
        )

        # level outline
        lvl_circle = Image.new("RGBA", (raw_length, raw_length))
        draw_lvl_circle = ImageDraw.Draw(lvl_circle)
        draw_lvl_circle.ellipse(
            [0, 0, raw_length, raw_length],
            fill=(badge_fill[0], badge_fill[1], badge_fill[2], 180),
            outline=(255, 255, 255, 250),
        )
        # determines exp bar color
        if "profile_exp_color" not in userinfo.keys() or not userinfo["profile_exp_color"]:
            exp_fill = (255, 255, 255, 230)
        else:
            exp_fill = tuple(userinfo["profile_exp_color"])
        draw_lvl_circle.pieslice(
            [0, 0, raw_length, raw_length], start_angle, angle, fill=exp_fill, outline=(255, 255, 255, 255),
        )
        # put on level bar circle
        lvl_circle = lvl_circle.resize((lvl_circle_dia, lvl_circle_dia), Image.ANTIALIAS)
        lvl_bar_mask = mask.resize((lvl_circle_dia, lvl_circle_dia), Image.ANTIALIAS)
        process.paste(lvl_circle, (circle_left, circle_top), lvl_bar_mask)

        # draws boxes
        draw.rectangle([(5, 133), (100, 285)], fill=badge_fill)  # badges
        draw.rectangle([(10, 138), (95, 168)], fill=rep_fill)  # reps

        total_gap = 10
        # border = int(total_gap / 2)
        profile_size = lvl_circle_dia - total_gap
        # raw_length = profile_size * multiplier
        # put in profile picture
        total_gap = 6
        border = int(total_gap / 2)
        profile_size = lvl_circle_dia - total_gap
        mask = mask.resize((profile_size, profile_size), Image.ANTIALIAS)
        profile_image = profile_image.resize((profile_size, profile_size), Image.ANTIALIAS)
        process.paste(profile_image, (circle_left + border, circle_top + border), mask)

        # write label text
        white_color = (240, 240, 240, 255)
        light_color = (160, 160, 160, 255)

        head_align = 105
        _write_unicode(
            self._truncate_text(self._name(user, 22), 22),
            head_align,
            vert_pos + 3,
            level_label_fnt,
            header_u_fnt,
            (110, 110, 110, 255),
        )  # NAME
        _write_unicode(userinfo["title"], head_align, 136, level_label_fnt, header_u_fnt, white_color)

        # draw level box
        level_right = 290
        level_left = level_right - 78
        draw.rectangle(
            [(level_left, 0), (level_right, 21)], fill=(badge_fill[0], badge_fill[1], badge_fill[2], 160),
        )  # box
        lvl_text = "LEVEL {}".format(userinfo["servers"][str(server.id)]["level"])
        if badge_fill == (128, 151, 165, 230):
            lvl_color = white_color
        else:
            lvl_color = self._contrast(badge_fill, rep_fill, exp_fill)
        draw.text(
            (self._center(level_left + 2, level_right, lvl_text, level_label_fnt), 2),
            lvl_text,
            font=level_label_fnt,
            fill=(lvl_color[0], lvl_color[1], lvl_color[2], 255),
        )  # Level #

        rep_text = "{} REP".format(userinfo["rep"])
        draw.text(
            (self._center(7, 100, rep_text, rep_fnt), 144), rep_text, font=rep_fnt, fill=white_color,
        )

        exp_text = "{}/{}".format(
            userinfo["servers"][str(server.id)]["current_exp"],
            self._required_exp(userinfo["servers"][str(server.id)]["level"]),
        )  # Exp
        exp_color = exp_fill
        draw.text((105, 99), exp_text, font=exp_fnt, fill=(exp_color[0], exp_color[1], exp_color[2], 255))  # Exp Text

        # determine info text color
        dark_text = (35, 35, 35, 230)
        info_text_color = self._contrast(info_color, light_color, dark_text)

        # lvl_left = 100
        label_align = 105
        _write_unicode("Rank:", label_align, 165, general_info_fnt, general_info_u_fnt, info_text_color)
        draw.text((label_align, 180), "Exp:", font=general_info_fnt, fill=info_text_color)  # Exp
        draw.text((label_align, 195), "Credits:", font=general_info_fnt, fill=info_text_color)  # Credits

        # local stats
        num_local_align = 172
        # local_symbol = "\U0001F3E0 "
        if "linux" in platform.system().lower():
            local_symbol = "\U0001F3E0 "
        else:
            local_symbol = "S "

        s_rank_txt = local_symbol + self._truncate_text(f"#{await self._find_server_rank(user, server)}", 8)
        _write_unicode(
            s_rank_txt,
            num_local_align - general_info_u_fnt.getsize(local_symbol)[0],
            165,
            general_info_fnt,
            general_info_u_fnt,
            info_text_color,
        )  # Rank

        s_exp_txt = self._truncate_text(f"{await self._find_server_exp(user, server)}", 8)
        _write_unicode(s_exp_txt, num_local_align, 180, general_info_fnt, general_info_u_fnt, info_text_color)  # Exp
        credits = await bank.get_balance(user)
        credit_txt = "${}".format(credits)
        draw.text(
            (num_local_align, 195), self._truncate_text(credit_txt, 18), font=general_info_fnt, fill=info_text_color,
        )  # Credits

        # global stats
        num_align = 230
        if "linux" in platform.system().lower():
            global_symbol = "\U0001F30E "
            fine_adjust = 1
        else:
            global_symbol = "G "
            fine_adjust = 0

        global_rank = await self._find_global_rank(user)
        rank_number = global_rank if global_rank else "1000+"
        rank_txt = global_symbol + self._truncate_text(f"#{rank_number}", 8)
        exp_txt = self._truncate_text(f"{userinfo['total_exp']}", 8)
        _write_unicode(
            rank_txt,
            num_align - general_info_u_fnt.getsize(global_symbol)[0] + fine_adjust,
            165,
            general_info_fnt,
            general_info_u_fnt,
            info_text_color,
        )  # Rank
        _write_unicode(exp_txt, num_align, 180, general_info_fnt, general_info_u_fnt, info_text_color)  # Exp

        draw.text((105, 220), "Info Box", font=sub_header_fnt, fill=white_color)  # Info Box
        margin = 105
        offset = 238
        for line in textwrap.wrap(userinfo["info"], width=42):
            await asyncio.sleep(0)
            # draw.text((margin, offset), line, font=text_fnt, fill=(70,70,70,255))
            _write_unicode(line, margin, offset, text_fnt, text_u_fnt, info_text_color)
            offset += text_fnt.getsize(line)[1] + 2

        # sort badges
        priority_badges = []

        for badgename in userinfo["badges"].keys():
            await asyncio.sleep(0)
            badge = userinfo["badges"][badgename]
            priority_num = badge["priority_num"]
            if priority_num != 0 and priority_num != -1:
                priority_badges.append((badge, priority_num))
        sorted_badges = sorted(priority_badges, key=operator.itemgetter(1), reverse=True)

        # TODO: simplify this. it shouldn't be this complicated... sacrifices conciseness for customizability
        if await self.config.badge_type() == "circles":
            # circles require antialiasing
            vert_pos = 171
            right_shift = 0
            left = 9 + right_shift
            # right = 52 + right_shift
            size = 27
            total_gap = 4  # /2
            hor_gap = 3
            vert_gap = 2
            border_width = int(total_gap / 2)
            mult = [
                (0, 0),
                (1, 0),
                (2, 0),
                (0, 1),
                (1, 1),
                (2, 1),
                (0, 2),
                (1, 2),
                (2, 2),
                (0, 3),
                (1, 3),
                (2, 3),
            ]
            i = 0
            for pair in sorted_badges[:12]:
                try:
                    coord = (
                        left + int(mult[i][0]) * int(hor_gap + size),
                        vert_pos + int(mult[i][1]) * int(vert_gap + size),
                    )
                    badge = pair[0]
                    bg_color = badge["bg_img"]
                    border_color = badge["border_color"]
                    multiplier = 6  # for antialiasing
                    raw_length = size * multiplier

                    # draw mask circle
                    mask = Image.new("L", (raw_length, raw_length), 0)
                    draw_thumb = ImageDraw.Draw(mask)
                    draw_thumb.ellipse((0, 0) + (raw_length, raw_length), fill=255, outline=0)

                    # check image
                    badge_image = await self._valid_image_url(bg_color)
                    if not badge_image:
                        continue

                    badge_image = badge_image.resize((raw_length, raw_length), Image.ANTIALIAS)

                    # structured like this because if border = 0, still leaves outline.
                    if border_color:
                        square = Image.new("RGBA", (raw_length, raw_length), border_color)
                        # put border on ellipse/circle
                        output = ImageOps.fit(square, (raw_length, raw_length), centering=(0.5, 0.5))
                        output = output.resize((size, size), Image.ANTIALIAS)
                        outer_mask = mask.resize((size, size), Image.ANTIALIAS)
                        process.paste(output, coord, outer_mask)

                        # put on ellipse/circle
                        output = ImageOps.fit(badge_image, (raw_length, raw_length), centering=(0.5, 0.5))
                        output = output.resize((size - total_gap, size - total_gap), Image.ANTIALIAS)
                        inner_mask = mask.resize((size - total_gap, size - total_gap), Image.ANTIALIAS)
                        process.paste(
                            output, (coord[0] + border_width, coord[1] + border_width), inner_mask,
                        )
                    else:
                        # put on ellipse/circle
                        output = ImageOps.fit(badge_image, (raw_length, raw_length), centering=(0.5, 0.5))
                        output = output.resize((size, size), Image.ANTIALIAS)
                        outer_mask = mask.resize((size, size), Image.ANTIALIAS)
                        process.paste(output, coord, outer_mask)
                except:
                    pass
                i += 1
        elif await self.config.badge_type() == "bars":
            vert_pos = 187
            i = 0
            for pair in sorted_badges[:5]:
                badge = pair[0]
                bg_color = badge["bg_img"]
                border_color = badge["border_color"]
                left_pos = 10
                right_pos = 95
                total_gap = 4
                border_width = int(total_gap / 2)
                bar_size = (85, 15)

                # check image
                badge_image = await self._valid_image_url(bg_color)
                if not badge_image:
                    continue

                if border_color is not None:
                    draw.rectangle(
                        [(left_pos, vert_pos + i * 17), (right_pos, vert_pos + 15 + i * 17)],
                        fill=border_color,
                        outline=border_color,
                    )  # border
                    badge_image = badge_image.resize(
                        (bar_size[0] - total_gap + 1, bar_size[1] - total_gap + 1), Image.ANTIALIAS,
                    )
                    process.paste(
                        badge_image, (left_pos + border_width, vert_pos + border_width + i * 17),
                    )
                else:
                    badge_image = badge_image.resize(bar_size, Image.ANTIALIAS)
                    process.paste(badge_image, (left_pos, vert_pos + i * 17))

                vert_pos += 3  # spacing
                i += 1

        image_object = BytesIO()
        result = Image.alpha_composite(result, process)
        result.save(image_object, format="PNG")
        image_object.seek(0)
        return discord.File(image_object, f"profile_{user.id}_{server.id}_{int(datetime.now().timestamp())}.png")

    # returns color that contrasts better in background
    def _contrast(self, bg_color, color1, color2):
        color1_ratio = self._contrast_ratio(bg_color, color1)
        color2_ratio = self._contrast_ratio(bg_color, color2)
        if color1_ratio >= color2_ratio:
            return color1
        else:
            return color2

    @staticmethod
    def _luminance(color):
        # convert to greyscale
        luminance = float((0.2126 * color[0]) + (0.7152 * color[1]) + (0.0722 * color[2]))
        return luminance

    def _contrast_ratio(self, bgcolor, foreground):
        f_lum = float(self._luminance(foreground) + 0.05)
        bg_lum = float(self._luminance(bgcolor) + 0.05)

        if bg_lum > f_lum:
            return bg_lum / f_lum
        else:
            return f_lum / bg_lum

    # returns a string with possibly a nickname
    def _name(self, user, max_length):
        if user.name == user.display_name:
            return user.name
        else:
            return "{} ({})".format(
                user.name, self._truncate_text(user.display_name, max_length - len(user.name) - 3), max_length,
            )

    @staticmethod
    async def _add_dropshadow(image, offset=(4, 4), background=0x000, shadow=0x0F0, border=3, iterations=5):
        totalWidth = image.size[0] + abs(offset[0]) + 2 * border
        totalHeight = image.size[1] + abs(offset[1]) + 2 * border
        back = Image.new(image.mode, (totalWidth, totalHeight), background)

        # Place the shadow, taking into account the offset from the image
        shadowLeft = border + max(offset[0], 0)
        shadowTop = border + max(offset[1], 0)
        back.paste(shadow, [shadowLeft, shadowTop, shadowLeft + image.size[0], shadowTop + image.size[1]])

        n = 0
        while n < iterations:
            back = back.filter(ImageFilter.BLUR)
            n += 1

        # Paste the input image onto the shadow backdrop
        imageLeft = border - min(offset[0], 0)
        imageTop = border - min(offset[1], 0)
        back.paste(image, (imageLeft, imageTop))
        return back

    async def draw_rank(self, user, server):
        # fonts
        # font_file = f"{bundled_data_path(self)}/font.ttf"
        font_bold_file = f"{bundled_data_path(self)}/font_bold.ttf"
        font_unicode_file = f"{bundled_data_path(self)}/unicode.ttf"
        name_fnt = ImageFont.truetype(font_bold_file, 22)
        header_u_fnt = ImageFont.truetype(font_unicode_file, 18)
        # sub_header_fnt = ImageFont.truetype(font_bold_file, 14)
        # badge_fnt = ImageFont.truetype(font_bold_file, 12)
        # large_fnt = ImageFont.truetype(font_bold_file, 33)
        level_label_fnt = ImageFont.truetype(font_bold_file, 22)
        general_info_fnt = ImageFont.truetype(font_bold_file, 15)
        # general_info_u_fnt = ImageFont.truetype(font_unicode_file, 11)
        # credit_fnt = ImageFont.truetype(font_bold_file, 10)

        def _write_unicode(text, init_x, y, font, unicode_font, fill):
            write_pos = init_x

            for char in text:
                if char.isalnum() or char in string.punctuation or char in string.whitespace:
                    draw.text((write_pos, y), char, font=font, fill=fill)
                    write_pos += font.getsize(char)[0]
                else:
                    draw.text((write_pos, y), "{}".format(char), font=unicode_font, fill=fill)
                    write_pos += unicode_font.getsize(char)[0]

        userinfo = await self.db.users.find_one({"user_id": str(user.id)})
        # get urls
        bg_url = userinfo["rank_background"]
        server_icon_url = server.icon_url_as(format="png", size=256)

        # guild icon image
        if not server_icon_url._url:
            server_icon = f"{bundled_data_path(self)}/defaultguildicon.png"
        else:
            server_icon = BytesIO()
            try:
                await server_icon_url.save(server_icon, seek_begin=True)
            except discord.HTTPException:
                server_icon = f"{bundled_data_path(self)}/defaultguildicon.png"

        # rank bg image
        async with self.session.get(bg_url) as r:
            image = await r.content.read()
        rank_background = BytesIO(image)

        # user icon image
        rank_avatar = BytesIO()
        try:
            await user.avatar_url.save(rank_avatar, seek_begin=True)
        except discord.HTTPException:
            rank_avatar = f"{bundled_data_path(self)}/defaultavatar.png"

        # set all to RGBA
        bg_image = Image.open(rank_background).convert("RGBA")
        profile_image = Image.open(rank_avatar).convert("RGBA")
        server_icon_image = Image.open(server_icon).convert("RGBA")

        # set canvas
        width = 360
        height = 100
        bg_color = (255, 255, 255, 0)
        result = Image.new("RGBA", (width, height), bg_color)
        process = Image.new("RGBA", (width, height), bg_color)

        # puts in background
        bg_image = bg_image.resize((width, height), Image.ANTIALIAS)
        bg_image = bg_image.crop((0, 0, width, height))
        result.paste(bg_image, (0, 0))

        # draw
        draw = ImageDraw.Draw(process)

        # draw transparent overlay
        vert_pos = 5
        left_pos = 70
        right_pos = width - vert_pos
        title_height = 22
        gap = 3

        draw.rectangle(
            [(left_pos - 20, vert_pos), (right_pos, vert_pos + title_height)], fill=(230, 230, 230, 230),
        )  # title box
        content_top = vert_pos + title_height + gap
        content_bottom = 100 - vert_pos

        if "rank_info_color" in userinfo.keys():
            info_color = tuple(userinfo["rank_info_color"])
            info_color = (
                info_color[0],
                info_color[1],
                info_color[2],
                160,
            )  # increase transparency
        else:
            info_color = (30, 30, 30, 160)
        draw.rectangle(
            [(left_pos - 20, content_top), (right_pos, content_bottom)], fill=info_color, outline=(180, 180, 180, 180),
        )  # content box

        # stick in credits if needed
        # if bg_url in bg_credits.keys():
        # credit_text = " ".join("{}".format(bg_credits[bg_url]))
        # draw.text((2, 92), credit_text,  font=credit_fnt, fill=(0,0,0,190))

        # draw level circle
        multiplier = 6
        lvl_circle_dia = 94
        circle_left = 15
        circle_top = int((height - lvl_circle_dia) / 2)
        raw_length = lvl_circle_dia * multiplier

        # create mask
        mask = Image.new("L", (raw_length, raw_length), 0)
        draw_thumb = ImageDraw.Draw(mask)
        draw_thumb.ellipse((0, 0) + (raw_length, raw_length), fill=255, outline=0)

        # drawing level bar calculate angle
        start_angle = -90  # from top instead of 3oclock
        angle = (
            int(
                360
                * (
                    userinfo["servers"][str(server.id)]["current_exp"]
                    / self._required_exp(userinfo["servers"][str(server.id)]["level"])
                )
            )
            + start_angle
        )

        lvl_circle = Image.new("RGBA", (raw_length, raw_length))
        draw_lvl_circle = ImageDraw.Draw(lvl_circle)
        draw_lvl_circle.ellipse([0, 0, raw_length, raw_length], fill=(180, 180, 180, 180), outline=(255, 255, 255, 220))
        # determines exp bar color
        if "rank_exp_color" not in userinfo.keys() or not userinfo["rank_exp_color"]:
            exp_fill = (255, 255, 255, 230)
        else:
            exp_fill = tuple(userinfo["rank_exp_color"])
        draw_lvl_circle.pieslice(
            [0, 0, raw_length, raw_length], start_angle, angle, fill=exp_fill, outline=(255, 255, 255, 230),
        )
        # put on level bar circle
        lvl_circle = lvl_circle.resize((lvl_circle_dia, lvl_circle_dia), Image.ANTIALIAS)
        lvl_bar_mask = mask.resize((lvl_circle_dia, lvl_circle_dia), Image.ANTIALIAS)
        process.paste(lvl_circle, (circle_left, circle_top), lvl_bar_mask)

        # draws mask
        total_gap = 10
        border = int(total_gap / 2)
        profile_size = lvl_circle_dia - total_gap
        raw_length = profile_size * multiplier
        # put in profile picture
        output = ImageOps.fit(profile_image, (raw_length, raw_length), centering=(0.5, 0.5))
        output.resize((profile_size, profile_size), Image.ANTIALIAS)
        mask = mask.resize((profile_size, profile_size), Image.ANTIALIAS)
        profile_image = profile_image.resize((profile_size, profile_size), Image.ANTIALIAS)
        process.paste(profile_image, (circle_left + border, circle_top + border), mask)

        # draw level box
        level_left = 274
        level_right = right_pos
        draw.rectangle([(level_left, vert_pos), (level_right, vert_pos + title_height)], fill="#AAA")  # box
        lvl_text = "LEVEL {}".format(userinfo["servers"][str(server.id)]["level"])
        draw.text(
            (self._center(level_left, level_right, lvl_text, level_label_fnt), vert_pos + 3),
            lvl_text,
            font=level_label_fnt,
            fill=(110, 110, 110, 255),
        )  # Level #

        # labels text colors
        white_text = (240, 240, 240, 255)
        dark_text = (35, 35, 35, 230)
        label_text_color = self._contrast(info_color, white_text, dark_text)

        # draw text
        grey_color = (110, 110, 110, 255)
        # white_color = (230, 230, 230, 255)

        # put in server picture
        server_size = content_bottom - content_top - 10
        server_border_size = server_size + 4
        radius = 20
        light_border = (150, 150, 150, 180)
        dark_border = (90, 90, 90, 180)
        border_color = self._contrast(info_color, light_border, dark_border)

        draw_server_border = Image.new(
            "RGBA", (server_border_size * multiplier, server_border_size * multiplier), border_color,
        )
        draw_server_border = self._add_corners(draw_server_border, int(radius * multiplier / 2))
        draw_server_border = draw_server_border.resize((server_border_size, server_border_size), Image.ANTIALIAS)
        server_icon_image = server_icon_image.resize(
            (server_size * multiplier, server_size * multiplier), Image.ANTIALIAS
        )
        server_icon_image = self._add_corners(server_icon_image, int(radius * multiplier / 2) - 10)
        server_icon_image = server_icon_image.resize((server_size, server_size), Image.ANTIALIAS)
        process.paste(
            draw_server_border, (circle_left + profile_size + 2 * border + 8, content_top + 3), draw_server_border,
        )
        process.paste(
            server_icon_image, (circle_left + profile_size + 2 * border + 10, content_top + 5), server_icon_image,
        )

        # name
        left_text_align = 130
        _write_unicode(
            self._truncate_text(self._name(user, 20), 20),
            left_text_align - 12,
            vert_pos + 3,
            name_fnt,
            header_u_fnt,
            grey_color,
        )  # Name

        # divider bar
        draw.rectangle([(187, 45), (188, 85)], fill=(160, 160, 160, 220))

        # labels
        label_align = 200
        draw.text((label_align, 38), "Server Rank:", font=general_info_fnt, fill=label_text_color)  # Server Rank
        draw.text((label_align, 58), "Server Exp:", font=general_info_fnt, fill=label_text_color)  # Server Exp
        draw.text((label_align, 78), "Credits:", font=general_info_fnt, fill=label_text_color)  # Credit
        # info
        right_text_align = 290
        rank_txt = f"#{await self._find_server_rank(user, server)}"
        draw.text(
            (right_text_align, 38), self._truncate_text(rank_txt, 12), font=general_info_fnt, fill=label_text_color,
        )  # Rank
        exp_txt = f"{await self._find_server_exp(user, server)}"
        draw.text(
            (right_text_align, 58), self._truncate_text(exp_txt, 12), font=general_info_fnt, fill=label_text_color,
        )  # Exp
        credits = await bank.get_balance(user)
        credit_txt = f"${credits}"
        draw.text(
            (right_text_align, 78), self._truncate_text(credit_txt, 12), font=general_info_fnt, fill=label_text_color,
        )  # Credits

        image_object = BytesIO()
        result = Image.alpha_composite(result, process)
        result.save(image_object, format="PNG")
        image_object.seek(0)
        return discord.File(image_object, f"rank_{user.id}_{server.id}_{int(datetime.now().timestamp())}.png")

    @staticmethod
    def _add_corners(im, rad, multiplier=6):
        raw_length = rad * 2 * multiplier
        circle = Image.new("L", (raw_length, raw_length), 0)
        draw = ImageDraw.Draw(circle)
        draw.ellipse((0, 0, raw_length, raw_length), fill=255)
        circle = circle.resize((rad * 2, rad * 2), Image.ANTIALIAS)

        alpha = Image.new("L", im.size, 255)
        w, h = im.size
        alpha.paste(circle.crop((0, 0, rad, rad)), (0, 0))
        alpha.paste(circle.crop((0, rad, rad, rad * 2)), (0, h - rad))
        alpha.paste(circle.crop((rad, 0, rad * 2, rad)), (w - rad, 0))
        alpha.paste(circle.crop((rad, rad, rad * 2, rad * 2)), (w - rad, h - rad))
        im.putalpha(alpha)
        return im

    async def draw_levelup(self, user, server):
        if not self._db_ready:
            return
        font_bold_file = f"{bundled_data_path(self)}/font_bold.ttf"
        userinfo = await self.db.users.find_one({"user_id": str(user.id)})
        # get urls
        bg_url = userinfo["levelup_background"]
        # profile_url = user.avatar_url

        # create image objects
        # bg_image = Image
        # profile_image = Image

        async with self.session.get(bg_url) as r:
            image = await r.content.read()

        level_background = BytesIO(image)
        level_avatar = BytesIO()
        try:
            await user.avatar_url.save(level_avatar, seek_begin=True)
        except discord.HTTPException:
            level_avatar = f"{bundled_data_path(self)}/defaultavatar.png"

        bg_image = Image.open(level_background).convert("RGBA")
        profile_image = Image.open(level_avatar).convert("RGBA")

        # set canvas
        width = 175
        height = 65
        bg_color = (255, 255, 255, 0)
        result = Image.new("RGBA", (width, height), bg_color)
        process = Image.new("RGBA", (width, height), bg_color)

        # draw
        draw = ImageDraw.Draw(process)

        # puts in background
        bg_image = bg_image.resize((width, height), Image.ANTIALIAS)
        bg_image = bg_image.crop((0, 0, width, height))
        result.paste(bg_image, (0, 0))

        # draw transparent overlay
        if "levelup_info_color" in userinfo.keys():
            info_color = tuple(userinfo["levelup_info_color"])
            info_color = (
                info_color[0],
                info_color[1],
                info_color[2],
                150,
            )  # increase transparency
        else:
            info_color = (30, 30, 30, 150)
        draw.rectangle([(38, 5), (170, 60)], fill=info_color)  # info portion

        # draw level circle
        multiplier = 6
        lvl_circle_dia = 60
        circle_left = 4
        circle_top = int((height - lvl_circle_dia) / 2)
        raw_length = lvl_circle_dia * multiplier

        # create mask
        mask = Image.new("L", (raw_length, raw_length), 0)
        draw_thumb = ImageDraw.Draw(mask)
        draw_thumb.ellipse((0, 0) + (raw_length, raw_length), fill=255, outline=0)

        # drawing level bar calculate angle
        # start_angle = -90  # from top instead of 3oclock

        lvl_circle = Image.new("RGBA", (raw_length, raw_length))
        draw_lvl_circle = ImageDraw.Draw(lvl_circle)
        draw_lvl_circle.ellipse([0, 0, raw_length, raw_length], fill=(255, 255, 255, 220), outline=(255, 255, 255, 220))

        # put on level bar circle
        lvl_circle = lvl_circle.resize((lvl_circle_dia, lvl_circle_dia), Image.ANTIALIAS)
        lvl_bar_mask = mask.resize((lvl_circle_dia, lvl_circle_dia), Image.ANTIALIAS)
        process.paste(lvl_circle, (circle_left, circle_top), lvl_bar_mask)

        # draws mask
        total_gap = 6
        border = int(total_gap / 2)
        profile_size = lvl_circle_dia - total_gap
        raw_length = profile_size * multiplier
        # put in profile picture
        output = ImageOps.fit(profile_image, (raw_length, raw_length), centering=(0.5, 0.5))
        # output = output.resize((profile_size, profile_size), Image.ANTIALIAS)
        mask = mask.resize((profile_size, profile_size), Image.ANTIALIAS)
        profile_image = profile_image.resize((profile_size, profile_size), Image.ANTIALIAS)
        process.paste(profile_image, (circle_left + border, circle_top + border), mask)

        # fonts
        # level_fnt2 = ImageFont.truetype(font_bold_file, 19)
        level_fnt = ImageFont.truetype(font_bold_file, 26)

        # write label text
        white_text = (240, 240, 240, 255)
        dark_text = (35, 35, 35, 230)
        level_up_text = self._contrast(info_color, white_text, dark_text)
        lvl_text = "LEVEL {}".format(userinfo["servers"][str(server.id)]["level"])
        draw.text(
            (self._center(50, 170, lvl_text, level_fnt), 22), lvl_text, font=level_fnt, fill=level_up_text,
        )  # Level Number

        image_object = BytesIO()
        result = Image.alpha_composite(result, process)
        result.save(image_object, format="PNG")
        image_object.seek(0)
        return discord.File(image_object, f"levelup_{user.id}_{server.id}_{int(datetime.now().timestamp())}.png")

    @commands.Cog.listener("on_message_without_command")
    async def _handle_on_message(self, message):
        server = message.guild
        user = message.author
        if not server or user.bot:
            return
        if await self.config.guild(server).disabled():
            return
        self._message_tasks.append([user, server, message])  # Add to task list

    async def process_tasks(self):  # Run all tasks and resets task list
        log.debug("_process_tasks is starting for batch xp writing")
        log.debug(f"DB ready state: {self._db_ready}")
        await self.bot.wait_until_red_ready()
        with contextlib.suppress(asyncio.CancelledError):
            while True:
                if not self._db_ready:
                    log.debug("_process_tasks has exited early because db is not ready")
                    await asyncio.sleep(5)
                    log.debug("_process_tasks is trying to connect again")
                    continue
                tasks = copy(self._message_tasks)
                self._message_tasks = []
                for a in tasks:
                    try:
                        await self._process_user_on_message(*a)
                        await asyncio.sleep(0.1)
                    except asyncio.CancelledError:
                        raise asyncio.CancelledError
                    except Exception as err:
                        log.error(
                            f"Error while giving XP to {a[0]}({a[0].id}) in {a[1]}({a[1].id})", exc_info=err,
                        )
                log.debug("Process task sleeping for 30 seconds")
                await asyncio.sleep(30)

    async def _process_user_on_message(self, user, server, message):  # Process a users message
        if not self._db_ready:
            log.debug("process_user_on_message has exited early because db is not ready")
            return
        text = message.content
        curr_time = time.time()
        log.debug(f"Processing {user} {server}")
        prefix = await self.bot.command_prefix(self.bot, message)
        # creates user if doesn't exist, bots are not logged.
        userinfo = await self._create_user(user, server)
        if not userinfo:
            return
        user_id = f"{user.id}"
        userinfo = await self.db.users.find_one({"user_id": user_id})
        # check if chat_block exists
        if "chat_block" not in userinfo:
            userinfo["chat_block"] = 0
        if "last_message" not in userinfo:
            userinfo["last_message"] = 0
        await asyncio.sleep(0)
        if all(
            [
                float(curr_time) - float(userinfo["chat_block"]) >= 120,
                not any(text.startswith(x) for x in prefix),
                len(message.content) > 10,
                message.content != userinfo["last_message"],
                message.channel.id not in await self.config.guild(server).ignored_channels(),
            ]
        ):
            log.debug(f"{user} {server}'s message qualifies for xp awarding")
            await asyncio.sleep(0)
            xp = await self.config.xp()
            await self._process_exp(message, server, userinfo, random.randint(xp[0], xp[1]))
            await asyncio.sleep(0)
            await self._give_chat_credit(user, server)
        else:
            log.debug(f"{user} {server}'s message DOES NOT qualify for xp awarding")

    async def _process_exp(self, message, server, userinfo, exp: int):
        if not self._db_ready:
            log.debug("process_exp has exited early because db is not ready")
            return
        server = message.guild if not None else server
        if not server:
            log.warning("Leveler is in _process_exp: server and message.guild are both None, skipping")
            return
        if not message.guild:
            log.warning(f"Leveler is in _process_exp and message.guild is None, trying {server}")
        channel = message.channel
        user = message.author
        # add to total exp
        try:
            required = self._required_exp(userinfo["servers"][str(server.id)]["level"])
        except Exception as e:
            log.warning(f"Error while determining XP for {user} in {server}\n", exc_info=e)
        try:
            await self.db.users.update_one(
                {"user_id": str(user.id)}, {"$set": {"total_exp": userinfo["total_exp"] + exp}}
            )
            await asyncio.sleep(0)
        except Exception as e:
            log.warning(f"Could not add XP to {user}!\n", exc_info=e)
        if userinfo["servers"][str(server.id)]["current_exp"] + exp >= required:
            await asyncio.sleep(0)
            userinfo["servers"][str(server.id)]["level"] += 1
            await self.db.users.update_one(
                {"user_id": str(user.id)},
                {
                    "$set": {
                        f"servers.{server.id}.level": userinfo["servers"][str(server.id)]["level"],
                        f"servers.{server.id}.current_exp": userinfo["servers"][str(server.id)]["current_exp"]
                        + exp
                        - required,
                        "chat_block": time.time(),
                        "last_message": message.content,
                    }
                },
            )
            await asyncio.sleep(0)
            await self._handle_levelup(user, userinfo, server, channel)
        else:
            await self.db.users.update_one(
                {"user_id": str(user.id)},
                {
                    "$set": {
                        f"servers.{server.id}.current_exp": userinfo["servers"][str(server.id)]["current_exp"] + exp,
                        "chat_block": time.time(),
                        "last_message": message.content,
                    }
                },
            )
            log.debug("process_exp has written the exp")

    async def _handle_levelup(self, user, userinfo, server, channel):
        if not self._db_ready:
            log.debug("_handle_levelup has exited early because db is not ready")
            return
        # channel lock implementation
        lock_channel_id = await self.config.guild(server).lvl_msg_lock()
        if lock_channel_id:
            lock_channel = self.bot.get_channel(lock_channel_id)
            if not lock_channel:
                await self.config.guild(server).lvl_msg_lock.set(None)
            else:
                channel = lock_channel

        server_identifier = ""  # super hacky
        name = await self._is_mention(user)  # also super hacky
        # private message takes precedent, of course
        if await self.config.guild(server).private_lvl_message():
            server_identifier = f" on {server.name}"
            channel = user
            name = "You"

        new_level = str(userinfo["servers"][str(server.id)]["level"])
        self.bot.dispatch("leveler_levelup", user, new_level)
        # add to appropriate role if necessary
        # try:
        server_roles = await self.db.roles.find_one({"server_id": str(server.id)})
        await asyncio.sleep(0)
        if server_roles is not None:
            for role in server_roles["roles"].keys():
                await asyncio.sleep(0)
                if int(server_roles["roles"][role]["level"]) == int(new_level):
                    await asyncio.sleep(0)
                    add_role = discord.utils.get(server.roles, name=role)
                    if add_role is not None:
                        await asyncio.sleep(0)
                        try:
                            await user.add_roles(add_role, reason="Levelup")
                        except discord.Forbidden:
                            await channel.send("Levelup role adding failed: Missing Permissions")
                        except discord.HTTPException:
                            await channel.send("Levelup role adding failed")
                    remove_role = discord.utils.get(server.roles, name=server_roles["roles"][role]["remove_role"])
                    if remove_role is not None:
                        await asyncio.sleep(0)
                        try:
                            await user.remove_roles(remove_role, reason="Levelup")
                        except discord.Forbidden:
                            await channel.send("Levelup role removal failed: Missing Permissions")
                        except discord.HTTPException:
                            await channel.send("Levelup role removal failed")
        try:
            server_linked_badges = await self.db.badgelinks.find_one({"server_id": str(server.id)})
            await asyncio.sleep(0)
            if server_linked_badges is not None:
                for badge_name in server_linked_badges["badges"]:
                    await asyncio.sleep(0)
                    if int(server_linked_badges["badges"][badge_name]) == int(new_level):
                        server_badges = await self.db.badges.find_one({"server_id": str(server.id)})
                        await asyncio.sleep(0)
                        if server_badges is not None and badge_name in server_badges["badges"].keys():
                            await asyncio.sleep(0)
                            userinfo_db = await self.db.users.find_one({"user_id": str(user.id)})
                            new_badge_name = "{}_{}".format(badge_name, server.id)
                            userinfo_db["badges"][new_badge_name] = server_badges["badges"][badge_name]
                            await self.db.users.update_one(
                                {"user_id": str(user.id)}, {"$set": {"badges": userinfo_db["badges"]}},
                            )
        except Exception as exc:
            await channel.send(f"Error. Badge was not given: {exc}")

        if await self.config.guild(server).lvl_msg():  # if lvl msg is enabled
            if await self.config.guild(server).text_only():
                if all(
                    [channel.permissions_for(server.me).send_messages, channel.permissions_for(server.me).embed_links,]
                ):
                    async with channel.typing():
                        em = discord.Embed(
                            description="**{} just gained a level{}! (LEVEL {})**".format(
                                name, server_identifier, new_level
                            ),
                            colour=user.colour,
                        )
                        await channel.send(embed=em)
            else:
                if all(
                    [channel.permissions_for(server.me).send_messages, channel.permissions_for(server.me).attach_files,]
                ):
                    async with channel.typing():
                        file = await self.draw_levelup(user, server)
                        await channel.send(
                            "**{} just gained a level{}!**".format(name, server_identifier), file=file,
                        )

    async def _find_server_rank(self, user, server):
        if not self._db_ready:
            return
        targetid = str(user.id)
        users = []
        q = f"servers.{server.id}"
        guild_ids = [str(x.id) for x in server.members]
        async for userinfo in self.db.users.find({q: {"$exists": "true"}}):
            await asyncio.sleep(0)
            if userinfo["user_id"] in guild_ids:
                try:
                    server_exp = 0
                    userid = userinfo["user_id"]
                    for i in range(userinfo["servers"][str(server.id)]["level"]):
                        server_exp += self._required_exp(i)
                    server_exp += userinfo["servers"][str(server.id)]["current_exp"]
                    users.append((userid, server_exp))
                except:
                    pass

        sorted_list = sorted(users, key=operator.itemgetter(1), reverse=True)

        rank = 1
        for a_user in sorted_list:
            await asyncio.sleep(0)
            if a_user[0] == targetid:
                return rank
            rank += 1

    async def _find_server_rep_rank(self, user, server):
        if not self._db_ready:
            return
        users = []
        q = f"servers.{server.id}"
        guild_ids = [str(x.id) for x in server.members]
        async for userinfo in self.db.users.find({"$and": [{q: {"$exists": "true"}}, {"rep": {"$gte": 1}}]}).sort(
            "rep", -1
        ):
            await asyncio.sleep(0)
            if userinfo["user_id"] in guild_ids:
                users.append((userinfo["user_id"], userinfo["rep"]))

        sorted_list = sorted(users, key=operator.itemgetter(1), reverse=True)

        rank = 1
        for a_user in sorted_list:
            await asyncio.sleep(0)
            if a_user[0] == str(user.id):
                return rank
            rank += 1

    async def _find_server_exp(self, user, server):
        if not self._db_ready:
            return
        server_exp = 0
        userinfo = await self.db.users.find_one({"user_id": str(user.id)})

        try:
            for i in range(userinfo["servers"][str(server.id)]["level"]):
                await asyncio.sleep(0)
                server_exp += self._required_exp(i)
            server_exp += userinfo["servers"][str(server.id)]["current_exp"]
            return server_exp
        except:
            return server_exp

    async def _find_global_rank(self, user):
        if not self._db_ready:
            return
        users = []

        async for userinfo in self.db.users.find(({"total_exp": {"$gte": 10}})).sort("total_exp", -1).limit(1000):
            await asyncio.sleep(0)
            try:
                users.append((userinfo["user_id"], userinfo["total_exp"]))
            except KeyError:
                pass
        sorted_list = sorted(users, key=operator.itemgetter(1), reverse=True)

        rank = 1
        for stats in sorted_list:
            await asyncio.sleep(0)
            if stats[0] == str(user.id):
                return rank
            rank += 1

    async def _find_global_rep_rank(self, user):
        if not self._db_ready:
            return
        users = []

        async for userinfo in self.db.users.find(({"rep": {"$gte": 1}})).sort("rep", -1).limit(1000):
            await asyncio.sleep(0)
            try:
                userid = userinfo["user_id"]
                users.append((userid, userinfo["rep"]))
            except KeyError:
                pass
        sorted_list = sorted(users, key=operator.itemgetter(1), reverse=True)

        rank = 1
        for stats in sorted_list:
            await asyncio.sleep(0)
            if stats[0] == str(user.id):
                return rank
            rank += 1

    # handles user creation, adding new server, blocking
    async def _create_user(self, user, server):
        if not self._db_ready:
            return
        # backgrounds = await self.get_backgrounds()   ... This wasn't used here
        try:
            user_id = f"{user.id}"
            userinfo = await self.db.users.find_one({"user_id": user_id})
            if not userinfo:
                default_profile = await self.config.default_profile()
                default_rank = await self.config.default_rank()
                default_levelup = await self.config.default_levelup()
                new_account = {
                    "user_id": user_id,
                    "username": user.name,
                    "servers": {},
                    "total_exp": 0,
                    "profile_background": default_profile,
                    "rank_background": default_rank,
                    "levelup_background": default_levelup,
                    "title": "",
                    "info": "I am a mysterious person.",
                    "rep": 0,
                    "badges": {},
                    "active_badges": {},
                    "rep_color": [],
                    "badge_col_color": [],
                    "rep_block": 0,
                    "chat_block": 0,
                    "last_message": "",
                    "profile_block": 0,
                    "rank_block": 0,
                }
                await self.db.users.insert_one(new_account)
                userinfo = await self.db.users.find_one({"user_id": user_id})

            if "username" not in userinfo or userinfo["username"] != user.name:
                await self.db.users.update_one({"user_id": user_id}, {"$set": {"username": user.name}}, upsert=True)

            if "servers" not in userinfo or str(server.id) not in userinfo["servers"]:
                await self.db.users.update_one(
                    {"user_id": user_id},
                    {"$set": {f"servers.{server.id}.level": 0, f"servers.{server.id}.current_exp": 0,}},
                    upsert=True,
                )
            return userinfo
        except AttributeError as err:
            log.debug("error in user creation", exc_info=err)
        except Exception as err:
            log.debug("error in user creation", exc_info=err)

    async def asyncit(self, iterable):
        for i in iterable:
            yield i
            await asyncio.sleep(0)

    @staticmethod
    def _truncate_text(text, max_length):
        if len(text) > max_length:
            if text.strip("$").isdigit():
                text = int(text.strip("$"))
                return "${:.2E}".format(text)
            return text[: max_length - 3] + "..."
        return text

    # finds the the pixel to center the text
    @staticmethod
    def _center(start, end, text, font):
        dist = end - start
        width = font.getsize(text)[0]
        start_pos = start + ((dist - width) / 2)
        return int(start_pos)

    # calculates required exp for next level
    @staticmethod
    def _required_exp(level: int):
        if level < 0:
            return 0
        return 139 * level + 65

    @staticmethod
    def _level_exp(level: int):
        return level * 65 + 139 * level * (level - 1) // 2

    @staticmethod
    def _find_level(total_exp):
        # this is specific to the function above
        return int((1 / 278) * (9 + math.sqrt(81 + 1112 * total_exp)))

    @staticmethod
    def char_in_font(unicode_char, font):
        for cmap in font["cmap"].tables:
            if cmap.isUnicode():
                if ord(unicode_char) in cmap.cmap:
                    return True
        return False

    @staticmethod
    def _is_hex(color: str):
        if color is not None and len(color) != 4 and len(color) != 7:
            return False

        reg_ex = r"^#(?:[0-9a-fA-F]{3}){1,2}$"
        return re.search(reg_ex, str(color))

    @checks.is_owner()
    @lvladmin.group()
    @commands.guild_only()
    async def convert(self, ctx):
        """Conversion commands."""
        pass

    @checks.is_owner()
    @convert.command(name="mee6levels")
    @commands.guild_only()
    async def mee6convertlevels(self, ctx, pages: int):
        """Convert Mee6 levels.
        Each page returns 999 users at most.
        This command must be run in a channel in the guild to be converted."""
        if await self.config.guild(ctx.guild).mentions():
            msg = (
                "**{}, levelup mentions are on in this server.**\n"
                "The bot will ping every user that will be leveled up through this process if you continue.\n"
                "Reply with `yes` if you want this conversion to continue.\n"
                "If not, reply with `no` and then run `{}lvladmin mention` to turn off mentions before running this command again."
            ).format(ctx.author.display_name, ctx.prefix)
            await ctx.send(msg)
            pred = MessagePredicate.yes_or_no(ctx)
            try:
                await self.bot.wait_for("message", check=pred, timeout=15)
            except TimeoutError:
                return await ctx.send("**Timed out waiting for a response.**")
            if pred.result is False:
                return await ctx.send("**Command cancelled.**")
        failed = 0
        for i in range(pages):
            await asyncio.sleep(0)
            async with self.session.get(
                f"https://mee6.xyz/api/plugins/levels/leaderboard/{ctx.guild.id}?page={i}&limit=999"
            ) as r:

                if r.status == 200:
                    data = await r.json()
                else:
                    return await ctx.send("No data was found within the Mee6 API.")

            for userdata in data["players"]:
                await asyncio.sleep(0)
                # _handle_levelup requires a Member
                user = ctx.guild.get_member(int(userdata["id"]))

                if not user:
                    failed += 1
                    continue

                level = userdata["level"]
                server = ctx.guild
                channel = ctx.channel

                # creates user if doesn't exist
                await self._create_user(user, server)
                userinfo = await self.db.users.find_one({"user_id": str(user.id)})

                # get rid of old level exp
                old_server_exp = 0
                for _i in range(userinfo["servers"][str(server.id)]["level"]):
                    await asyncio.sleep(0)
                    old_server_exp += self._required_exp(_i)
                userinfo["total_exp"] -= old_server_exp
                userinfo["total_exp"] -= userinfo["servers"][str(server.id)]["current_exp"]

                # add in new exp
                total_exp = self._level_exp(level)
                userinfo["servers"][str(server.id)]["current_exp"] = 0
                userinfo["servers"][str(server.id)]["level"] = level
                userinfo["total_exp"] += total_exp

                await self.db.users.update_one(
                    {"user_id": str(user.id)},
                    {
                        "$set": {
                            "servers.{}.level".format(server.id): level,
                            "servers.{}.current_exp".format(server.id): 0,
                            "total_exp": userinfo["total_exp"],
                        }
                    },
                )
                await self._handle_levelup(user, userinfo, server, channel)
        await ctx.send(f"{failed} users could not be found and were skipped.")

    @checks.is_owner()
    @convert.command(name="mee6ranks")
    @commands.guild_only()
    async def mee6convertranks(self, ctx):
        """Convert Mee6 role rewards.
        This command must be run in a channel in the guild to be converted."""
        async with self.session.get(f"https://mee6.xyz/api/plugins/levels/leaderboard/{ctx.guild.id}") as r:
            if r.status == 200:
                data = await r.json()
            else:
                return await ctx.send("No data was found within the Mee6 API.")
        server = ctx.guild
        remove_role = None
        for role in data["role_rewards"]:
            await asyncio.sleep(0)
            role_name = role["role"]["name"]
            level = role["rank"]

            role_obj = discord.utils.find(lambda rol: rol.name == role_name, server.roles)
            if role_obj is None:
                await ctx.send("**Please make sure the `{}` roles exist!**".format(role_name))
            else:
                server_roles = await self.db.roles.find_one({"server_id": str(server.id)})
                if not server_roles:
                    new_server = {
                        "server_id": str(server.id),
                        "roles": {role_name: {"level": str(level), "remove_role": remove_role}},
                    }
                    await self.db.roles.insert_one(new_server)
                else:
                    if role_name not in server_roles["roles"]:
                        server_roles["roles"][role_name] = {}

                    server_roles["roles"][role_name]["level"] = str(level)
                    server_roles["roles"][role_name]["remove_role"] = remove_role
                    await self.db.roles.update_one(
                        {"server_id": str(server.id)}, {"$set": {"roles": server_roles["roles"]}}
                    )

                await ctx.send("**The `{}` role has been linked to level `{}`**".format(role_name, level))

    @checks.is_owner()
    @convert.command(name="tatsulevels")
    @commands.guild_only()
    async def tatsumakiconvertlevels(self, ctx):
        """Convert Tatsumaki levels.
        This command must be run in a channel in the guild to be converted."""
        token = await self.bot.get_shared_api_tokens("tatsumaki")
        tatsu_token = token.get("api_key", False)
        if not tatsu_token:
            return await ctx.send(f"You do not have a valid Tatsumaki API key set up. "
                                  f"If you have a key, you can set it via `{ctx.clean_prefix}set api tatsumaki api_key <api_key_here>`\n"
                                  f"Keys are not currently available if you do not have one already as the API is in the process of being revamped.")

        if await self.config.guild(ctx.guild).mentions():
            msg = (
                "**{}, levelup mentions are on in this server.**\n"
                "The bot will ping every user that will be leveled up through this process if you continue.\n"
                "Reply with `yes` if you want this conversion to continue.\n"
                "If not, reply with `no` and then run `{}lvladmin mention` to turn off mentions before running this command again."
            ).format(ctx.author.display_name, ctx.prefix)
            await ctx.send(msg)
            pred = MessagePredicate.yes_or_no(ctx)
            try:
                await self.bot.wait_for("message", check=pred, timeout=15)
            except TimeoutError:
                return await ctx.send("**Timed out waiting for a response.**")
            if pred.result is False:
                return await ctx.send("**Command cancelled.**")
        failed = 0
        await asyncio.sleep(0)
        async with self.session.get(
            f"https://api.tatsumaki.xyz/guilds/{ctx.guild.id}/leaderboard?limit&=-1"
        ) as r:

            if r.status == 200:
                data = await r.json()
            else:
                return await ctx.send("No data was found within the Tastumaki API.")

        for userdata in data:
            if userdata is None:
                continue
            await asyncio.sleep(0)
            # _handle_levelup requires a Member
            user = ctx.guild.get_member(int(userdata["user_id"]))

            if not user:
                failed += 1
                continue

            level = self._find_level(userdata["score"])
            server = ctx.guild
            channel = ctx.channel

            # creates user if doesn't exist
            await self._create_user(user, server)
            userinfo = await self.db.users.find_one({"user_id": str(user.id)})

            # get rid of old level exp
            old_server_exp = 0
            for _i in range(userinfo["servers"][str(server.id)]["level"]):
                await asyncio.sleep(0)
                old_server_exp += self._required_exp(_i)
            userinfo["total_exp"] -= old_server_exp
            userinfo["total_exp"] -= userinfo["servers"][str(server.id)]["current_exp"]

            # add in new exp
            total_exp = self._level_exp(level)
            userinfo["servers"][str(server.id)]["current_exp"] = 0
            userinfo["servers"][str(server.id)]["level"] = level
            userinfo["total_exp"] += total_exp

            await self.db.users.update_one(
                {"user_id": str(user.id)},
                {
                    "$set": {
                        "servers.{}.level".format(server.id): level,
                        "servers.{}.current_exp".format(server.id): 0,
                        "total_exp": userinfo["total_exp"],
                    }
                },
            )
            await self._handle_levelup(user, userinfo, server, channel)
        await ctx.send(f"{failed} users could not be found and were skipped.")
