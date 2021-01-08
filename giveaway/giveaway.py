import discord
import asyncio
from redbot.core import bot, commands, checks, Config
from redbot.core.utils.predicates import ReactionPredicate
from redbot.core.utils.menus import start_adding_reactions
from redbot.core.utils.chat_formatting import escape, italics, humanize_number
from redbot.core.bot import Red
from random import randint, choice
from typing import Union, Optional, Literal

class Giveaway(commands.Cog):
    """Emoji ID-Based Raffling, for a different style of raffling!"""
    default_guild = {   
        "emoji": "",
        "entrants": []
    }

    def __init__(self, bot: "Red"):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=44223194195)
        self.config.register_guild(**self.default_guild)
    async def red_delete_data_for_user(
        self,
        *,
        requester,
        user_id: int,
    ):
        
        pass # FOR NOW. We can manually remove as needed while I write a better removal tool.

    # Admin Commands!
    @commands.group()
    @commands.guild_only()
    @checks.mod_or_permissions(manage_messages=True)
    async def giveawayset(self, ctx):
        """Configure Options for the raffler"""
        #And So, the nightmare begins.

    @checks.mod_or_permissions(manage_messages=True)
    @giveawayset.command()
    async def emoji(self, ctx, emoji_target: discord.PartialEmoji):
        """Set the Emoji target for the raffler
        to hunt for When doing a `raffle collect`"""
        #emoji_new = self.fix_custom_emoji(emoji_target) # Handles if we've fed it a custom emoji or not.
        try:
            emoji_new = str(emoji_target) #Or we can just cast to a string. makes a lot more sense.
            guild = ctx.guild
            settings = self.config.guild(guild)
            await ctx.send(f"{emoji_new}")
            await settings.emoji.set(emoji_new) #Emoji Saved here. Thank lord. 
            await ctx.send(f"Emoji locked in as {emoji_new}")
        except:
            await ctx.send("`Error: Emoji Couldn't be cast into a string. I'd double check that WAS an emoji, honestly..`")

        ## Free Space for more admin commands here. 

    @commands.group()
    @commands.guild_only()
    @checks.mod_or_permissions(manage_messages=True)
    async def giveaway(self, ctx):
        """The main giveaway!"""

    @checks.mod_or_permissions(manage_messages=True)
    @giveaway.command()
    async def compile(self, ctx, channel: discord.TextChannel, *ids: int):    
        """Compile reactions from given IDs to match the target emoji"""
        guild = ctx.guild
        counter = 0
        messages = ids
        settings = self.config.guild(guild)  #The main backbone command, this kinda does everything ever.
        emoji_target = await settings.emoji()
        for m in messages:                   
            message_to_check = m
            try:
                msg = await channel.fetch_message(message_to_check)
                reaction = next(filter(lambda x: str(x.emoji) == emoji_target, msg.reactions), None)
                users = [user for user in await reaction.users().flatten() if guild.get_member(user.id)]
            # To this point, we have (line 60): grabbed a list of message ID's in a channel, and (line 68): started grabbing each one, one-by-one.
            # We're Then (line 69): using a lambda to grab Users of whoever reacted with the target emoji, so that (line 70): we can flatten them to
            #Normal User objects. Now we handle no one reacting...
                if reaction is None: 
                    return await ctx.send("Nobody has reacted with that emoji, so that won't work.")
            # ... and then store the users that have reacted.
                for u in users:
                    user_to_add = u.id
                    counter = counter + 1
                    entrants = await settings.entrants()
                    entrants.append(f"{user_to_add}")    
                    await settings.entrants.set (entrants)
                await ctx.send(f"{counter} Users added to the entrants list")
            except:
                await ctx.send(f"Error with {message_to_check}: Thats not a valid ID. please give *Message ID's* If the message ID's are valid, try making sure you're referencing the right channel.")



    @checks.mod_or_permissions(manage_messages=True)
    @giveaway.command()
    async def clear(self, ctx):
        """Clears the current Entries from the Server."""
        guild = ctx.guild
        settings = self.config.guild(guild)
        msg = await ctx.send("Confirm: Delete Current Entrants list for this server?")
        start_adding_reactions(msg, ReactionPredicate.YES_OR_NO_EMOJIS) #Reaction Predicates save a stupidly large amount of use, its almost scary.
        pred = ReactionPredicate.yes_or_no(msg, ctx.author)
        await ctx.bot.wait_for("reaction_add", check=pred)
        if pred.result is True:
            entrants = []
            await settings.entrants.set(entrants)
            await ctx.send("Entrants for this server have been cleared")
        else:
            await ctx.send("Alright then, cancelling that command...")
            asyncio.sleep(2) # Because why not
            await ctx.send("Done!")
            

    @checks.mod_or_permissions(manage_messages=True)
    @giveaway.command()
    async def draw(self, ctx):
        """Bread 'n' Butter, cant have a raffler that doesnt draw a winner!"""
        guild = ctx.guild
        settings = self.config.guild(guild)
        await ctx.send(":drum:") #Animated Drumkit when
        entrants = await settings.entrants()
        hopefuls = [escape(e, mass_mentions=True) for e in entrants] #So someone named @everyone cant @everyone
        winner_id = int(choice(hopefuls))
        winner = ctx.bot.get_user(winner_id) #Coulda just passed bot through the cog, but this is the only case needed so no point 
        await ctx.send("And the winner is.....")
        asyncio.sleep(2) #This is supposed to be seconds. Async is a liar. 
        await ctx.send(f"{winner.mention}! Come and get your Prize!") #Double benefit is that ctx also santizes so its an extra "guy cant call himself @everyone"
                                                                    # And use the bot to ping everyone, Right Masonic? I mean, Right @@here?


## Created By Dan.
