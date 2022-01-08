from pyzbar.pyzbar import decode
from PIL import Image
import requests
from io import BytesIO
import discord
import re

async def QRScanner(message: discord.Message, data: str):
    """Main Logic for actually handling the QR Codes. Actually quite simple."""
    if discord.Asset(data):
        response = discord.Asset.read(data)
    else:
        valid = re.search("(?i)http(?::\/\/|s:\/\/).*(?:twimg|png|jpg|jpeg|)", data)
    decodedImage = decode(Image.open(BytesIO(response.content)))
    AreWeThereYet = str(decodedImage[0])
    QRURL = AreWeThereYet.partition("data=b'")[2].partition("',")[0]
    TheRealQRURL = (f"`{QRURL}`")

    await message.channel.send(TheRealQRURL)

