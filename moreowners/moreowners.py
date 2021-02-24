import discord
import asyncio
from redbot.core import checks, commands, Config 
from redbot.core.bot import Red 

# Danstr, Masonic, and thanks Sinbad for pointing out this is possible.
class MoreOwners(commands.Cog):

    default_global = {"owners": []}

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=1189998819991197253) 

        self.config.register_global(**self.default_global)

        self.owner_ids = []

        self._originalOwnerCheck = self.bot.is_owner

        self._applyOverride()

        asyncio.ensure_future(self._refreshOwners()) # Refresh owners on startup to populate array

    async def red_delete_data_for_user(self, *, requester, user_id):
        return # We.. can't really do that here.

    def cog_unload(self):
        self._removeOverride() #Make sure original check implementation is returned after cog unloads

    def _removeOverride(self):
        self.bot.is_owner = self._originalOwnerCheck #We Grabbed this on init, remember? means we've got a hard copy of the actual owner.
                                                     #This May not behave properly if Red is set to recognise team members as owners.

    def _applyOverride(self):
        self.bot.is_owner = self._createOverride(self.bot.is_owner, self._altIsOwner)

    def _altIsOwner(self, author):
        return str(author.id) in self.owner_ids 

    def _createOverride(self, ogFunc, altFunc):
        async def isOwnerOrCoOwner(author):
            if await ogFunc(author):
                return True
            else:
                return altFunc(author)
        return isOwnerOrCoOwner

    async def _addOwner(self, uid):
        owners = await self.config.owners()
        owners.extend([str(uid)])
        await self.config.owners.set(owners)
        await self._refreshOwners()

    async def _revokeOwner(self, uid):
        owners = await self.config.owners()
        
        try:
            owners.remove(uid)
        except ValueError:
            pass

        await self.config.owners.set(owners)
        await self._refreshOwners()        

    async def _refreshOwners(self):
        self.owner_ids = await self.config.owners()

    @checks.is_owner()
    @commands.group()
    @commands.guild_only()
    async def owner(self, ctx):
        if ctx.invoked_subcommand is None:
            pass

    @checks.is_owner() #Because as funny as anyone being able to do this would be, Thats a bad idea. - Danstr
    @owner.command()
    async def grant(self, ctx, member: discord.Member):
        """ Format: `<p>ownergrant <id1> <id2> <id3>` etc..
        KEEP IN MIND THAT THIS WILL ADD OWNERS WITH FULL BOT ACCESS.
        Remember that the first tool of the trade is trust.
         """ #Not a joke, btw.
        member_id = str(member.id)
        if member_id in self.owner_ids:
            await ctx.send("This user is already an owner.")
            return

        await self._addOwner(member_id)
                
        await ctx.send(f"{member.display_name} has been added to the Owner list")

    @checks.is_owner()
    @owner.command()
    async def revoke(self, ctx, member: discord.Member):
        member_id = str(member.id)
        if not member_id in self.owner_ids:
            await ctx.send("This user is not an owner")
            return

        await self._revokeOwner(member_id)

        await ctx.send(f"{member.display_name} has had their access removed.")


    @checks.is_owner()
    @owner.command()
    async def check(self, ctx):
        """Only Responds to Owners."""
        await ctx.send("You are an owner!")

    @checks.is_owner()
    @owner.command()
    async def refreshowners(self, ctx):
        await self._refreshOwners()
        await ctx.send(f"Refreshed Owners, {str(self.owner_ids)} co-owners")

    @checks.is_owner()
    @owner.command()
    async def list(self, ctx):
        if len(self.owner_ids) == 0:
            await ctx.send(f"No additional owners")
            return

        owners = "Owners:"
        for oid in self.owner_ids:
            member = self.bot.get_user(int(oid))
            owners += "\n" + member.display_name

        await ctx.send(owners)

