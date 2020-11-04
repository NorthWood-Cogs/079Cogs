from .badge import Badge


def setup(bot):
    bot.add_cog(Badge(bot))
    # TODO - Add mydata support!
