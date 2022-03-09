import discord
from redbot.core import commands, checks, Config

class YetAnotherModLog(commands.Cog):
    """Oh How conveinient, the Acroynym's YAML"""
    def __init__(self, bot):
        super().__init__()
        self.bot = bot
        self.Config = Config.get_conf(self, IDENTIFIER="FUCKYOUMRFREEMAN", force_registration=True)
        default_guild= {
            "enabled": False,
            "embed": True,
            "channelID": 0}
        self.config.register_guild(default_guild)
    def EmbedBuilder(DeletedMsg, UserID):
        """Guess by the name"""
        em = discord.Embed(color="red", title=f"Deleted Message by {UserID}", description="DeletedMsg")
        return em
    @checks.admin_or_permissions(manage_guild=True)
    @commands.guild_only()
    @commands.group(name="mlset")
    async def _mlset(self, ctx):
        """Settings for ModLog. What did you expect?"""

    @_mlset.command(name="enable")
    async def _enable(self, ctx, toggle: bool):
        """Enable or disable the ModLog."""
        if toggle== True:
            settings = await self.Config.guild(ctx.guild)
            await settings.enabled.set(toggle)
    @_mlset.command(name="channel")
    async def _channel(self, ctx, channelID: int):
        """Fuck"""
        await self.Config.guild(ctx.guild).set({"channelID": channelID})

    #TODO : Other settings commands, for now we monkeypatching

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        """penis"""
        if message.content is not None:
            embed = self.EmbedBuilder(message.content, message.author)
            settings =await self.config.guild(message.channel.guild).all()
            lol = message.author.avatar.url
            if settings.enabled() == True:
                channel = discord.utils.get(message.channel.guild.channels, id=settings.channelID())
                channel.send(embed)