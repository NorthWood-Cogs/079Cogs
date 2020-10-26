"""Module for the Sticky cog."""

# Copyright (c) 2017-2018 Tobotimus
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import asyncio
import contextlib
import calendar
import time
from typing import Any, Dict, Optional, Union

import discord
from redbot.core import Config, checks, commands
from redbot.core.utils.menus import start_adding_reactions
from redbot.core.utils.predicates import ReactionPredicate

UNIQUE_ID = 0x6AFE8000


class Sticky(commands.Cog):
    """Sticky messages to your channels."""

    STICKY_DELAY = 3

    def __init__(self, bot):
        super().__init__()

        self.bot = bot
        self.conf = Config.get_conf(self, identifier=UNIQUE_ID, force_registration=True)
        self.conf.register_channel(
            stickied=None,  # This is for [p]sticky
            header_enabled=True,
            advstickied={"content": None, "embed": {}},  # This is for [p]stickyexisting
            last=None,
            last_post = 0,
            cooldown= 0,
        )
        self.locked_channels = set()

    @checks.mod_or_permissions(manage_messages=True)
    @commands.guild_only()
    @commands.group(invoke_without_command=True)
    async def sticky(self, ctx: commands.Context, cooldown: Optional[int] = 30, *, content: str):
        """Sticky a message to this channel. Stickys have a cooldown of 30 seconds by default before reposting."""
        channel = ctx.channel
        settings = self.conf.channel(channel)
        header_enabled = await settings.header_enabled()
        em_ToSend = discord.Embed(title="Stickied Message", description=f"{content}")
        #to_send = (
            #f"__***Stickied Message***__\n\n{content}" if header_enabled else content
        #)
        #msg = await channel.send(to_send)
        em = await ctx.send(embed=em_ToSend)

        await settings.set(
            {"stickied": content, "header_enabled": header_enabled, "last": em.id, "last_post": calendar.timegm(time.gmtime()), "cooldown": cooldown}
        )

    @checks.mod_or_permissions(manage_messages=True)
    @commands.guild_only()
    @commands.command()
    async def unsticky(self, ctx: commands.Context, force: bool = False):
        """Remove the sticky message from this channel.

        Deleting the sticky message will also unsticky it.

        Do `[p]unsticky yes` to skip the confirmation prompt.
        """
        channel = ctx.channel
        settings = self.conf.channel(channel)
        self.locked_channels.add(channel)
        settings_dict = await settings.all()
        try:
            last_id = await settings.last()
            if last_id is None:
                await ctx.send("There is no stickied message in this channel.")
                return
            msg = None
            if not force and channel.permissions_for(ctx.me).add_reactions:
                content = settings_dict["stickied"]
                msg = await ctx.send(
                    f"To Confirm, wipe the sticky `{content}` from `{channel}`?"
                )
                start_adding_reactions(msg, emojis=ReactionPredicate.YES_OR_NO_EMOJIS)

                pred = ReactionPredicate.yes_or_no(msg)
                try:
                    resp = await ctx.bot.wait_for(
                        "reaction_add", check=pred, timeout=30
                    )
                except asyncio.TimeoutError:
                    resp = None
                if resp is None or pred.result is False:
                    with contextlib.suppress(discord.NotFound):
                        await msg.delete()
                    return
            await settings.set(
                # Preserve the header setting
                {"header_enabled": await settings.header_enabled()}
            )
            with contextlib.suppress(discord.HTTPException):
                last = await channel.fetch_message(last_id)
                await last.delete()

            if msg is not None:
                await msg.delete()
            await ctx.tick()
        finally:
            self.locked_channels.remove(channel)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Event which checks for sticky messages to resend."""
        channel = message.channel
        settings = self.conf.channel(channel)
        settings_dict = await settings.all()
        old_time = settings_dict["last_post"]
        cooldown = settings_dict["cooldown"]
        timestamp = calendar.timegm(time.gmtime())
        if (timestamp - old_time) > cooldown:
            early_exit = (
                isinstance(channel, discord.abc.PrivateChannel)
                or channel in self.locked_channels
            )
            if early_exit:
                return
            settings = self.conf.channel(channel)
            last = await settings.last()
            if last is None or message.id == last:
                return
            try:
                last = await channel.fetch_message(last)
            except discord.NotFound:
                pass
            except discord.Forbidden:
                pass
            else:
                with contextlib.suppress(discord.NotFound):
                    await last.delete()
        else:
            pass


    @commands.Cog.listener()
    async def on_raw_message_delete(    
        self, payload: discord.raw_models.RawMessageDeleteEvent
    ):
        """If the stickied message was deleted, re-post it."""
        channel = self.bot.get_channel(payload.channel_id)
        settings = self.conf.channel(channel)
        settings_dict = await settings.all()
        if payload.message_id != settings_dict["last"]:
            return
        if settings_dict["stickied"] is not None:
            content = settings_dict["stickied"]
            em_ToSend = discord.Embed(title="Stickied Message", description=f"{content}")
            #to_send = f"__***Stickied Message***__\n\n{content}" if header else content
            #new = await channel.send(to_send)
            new = await channel.send(embed=em_ToSend)
        else:
            advstickied = settings_dict["advstickied"]
            if advstickied["content"] or advstickied["embed"]:
                return
            else:
                # The last stickied message was deleted but there's nothing to send
                await settings.last.clear()
                return

        timer = calendar.timegm(time.gmtime())
        await settings.last.set(new.id)
        await settings.last_post.set(timer)
