from .crasherbgone import CrasherBGone

async def setup(bot):
    cog = CrasherBGone()
    await cog.initialize()
    bot.add_cog(CrasherBGone(bot))