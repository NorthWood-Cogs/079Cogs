from .crasherbgone import CrasherBGone

async def setup(bot):
    cog = CrasherBGone(bot)
    await cog.initialize()
    bot.add_cog(CrasherBGone(bot))