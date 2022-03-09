from .yetanothermodlog import YetAnotherModLog


def setup(bot):
    """Load it!"""
    bot.add_cog(YetAnotherModLog(bot))
