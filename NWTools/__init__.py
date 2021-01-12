from .nwtools import NWTools

async def setup(bot):
    bot.add_cog(NWTools(bot))