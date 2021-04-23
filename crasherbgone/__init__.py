from .crasherbgone import CrasherBGone

async def setup(bot):
    bot.add_cog(CrasherBGone(bot))