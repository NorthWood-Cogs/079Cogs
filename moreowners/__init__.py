from .moreowners import MoreOwners

async def setup(bot):
    bot.add_cog(MoreOwners(bot))