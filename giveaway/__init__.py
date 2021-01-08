from .giveaway import Giveaway

def setup(bot):
    bot.add_cog(Giveaway(bot))