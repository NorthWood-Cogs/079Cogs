from .yetanothermodlog import yetAnotherModLog


def setup(bot):
    """Load it!"""
    bot.add_cog(yetAnotherModLog(bot))
