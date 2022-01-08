from .qrbeeper import QRBeeper


def setup(bot):
    bot.add_cog(QRBeeper(bot))
