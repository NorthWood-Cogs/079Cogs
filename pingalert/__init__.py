from .pingalert import PingAlert


def setup(bot):
    bot.add_cog(PingAlert(bot))