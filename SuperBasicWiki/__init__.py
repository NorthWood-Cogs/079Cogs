#Watch this space
from .wikishit import wikishite

__red_end_user_data_statement__="We store LITERALLY NOTHING. You're fine."


async def setup(bot):
    bot.add_cog(wikishite(bot))