from redbot.core import commands, Config, checks
from .notquitehelping import QRScanner
import discord


class QRBeeper(commands.Cog):
    """Automatic Per-Channel QR Code scanner.
    May work on Barcodes too, ironically.
    Can also be told to delete entries dependent on set values."""

    def __init__(self, bot):
        self.bot = bot

        self.Conff = Config.get_conf(self, identifier=4568471251472305778942644242, force_registration=True)
        default_channel = {
            "enabled": False,
            "DeleteOffenders": False,
            "DeleteList": [],
        }
        self.Conff.register_channel(**default_channel)



    @commands.group(name="qrset")
    @commands.guild_only()
    @checks.mod_or_permissions(manage_messages=True)
    async def _qrcodeset(self, ctx):
        """Settings for QRBeeper."""

    @_qrcodeset.command(name="toggle")
    async def _toggle(self, ctx):
        """Toggles the Automatic QR Scanner."""
        status = self.Conff.channel(ctx.channel).enabled()
        await ctx.reply(status)
        if status == True:
            #await self.Conff.channel(ctx.channel).enabled.set(False)
            await ctx.reply("QR Scanning Now **Disabled** In this channel.")
        if status == False: 
            #await self.Conff.channel(ctx.channel).enabled.set(True)
            await ctx.reply("QR Scanning Now **Enabled** In this channel.")

    @_qrcodeset.command(name="autodel")
    async def _autodelete(self, ctx):
        """Tells the bot to automatically delete A QR code if its link contains text from the blacklist."""
        status = self.Conff.channel(ctx.channel).DeleteOffenders()

        if status:
            await self.Conff.channel(ctx.channel).DeleteOffenders.set(False)
            await ctx.reply("No Longer deleting QR Codes if their contents are on the blacklist.")
        if not status:
            await self.Conff.channel(ctx.channel).DeleteOffenders.set(True)
            await ctx.reply("I am now deleting QR Codes if their contents are on the blacklist.")

    @_qrcodeset.group(name="list")
    async def _list(self, ctx):
        """Manage the Automatic delete List, or blacklist for short."""

    @_list.command(name="view")
    async def _list_view(self, ctx):
        """Posts the entire contents of the blacklist"""
        contents = self.Conff.channel(ctx.channel).DeleteList()

        await ctx.reply(f"""```{contents}```""")

    @_list.command(name="remove")
    async def _list_add(self, ctx, entry):
        """Removes an entry from the blacklist"""
        contents = self.Conff.channel(ctx.channel).DeleteList()
        try:
            entryToDelete = contents.index(entry)
            ToBeSaved = contents.pop(entryToDelete)
            await self.Conff.channel(ctx.channel).DeleteList.set(contents)
            await ctx.reply(f"removed {ToBeSaved} from the blacklist.")
        except ValueError:
            await ctx.reply("This wasn't on the list.")

    @_list.command(name="add")
    async def _list_add(self, ctx, entry):
        """Adds an entry to the blacklist"""
        contents = self.Conff.channel(ctx.channel).DeleteList()

        try:
            contents.append(entry)
            await self.Conff.channel(ctx.channel).DeleteList.set(contents)
            await ctx.reply(f"Added {entry} to the blacklist.")

        except:
            await ctx.reply("An error has occured. Weird.")
    

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.guild is None:
            return
        if await self.bot.cog_disabled_in_guild(self, message.guild):
            return
        
        author = message.author
        is_it_shit = isinstance(author, discord.Member) and not author.bot
        if not is_it_shit:
            return

        QR_result = await QRScanner(message.attachments[0].url)

        if QR_result == "Error":
            await message.channel.send("An Error Has occured within the QRScanner.")

        else:
            await message.channel.send(QR_result)
