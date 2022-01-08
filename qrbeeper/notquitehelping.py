from pyzbar.pyzbar import decode
from PIL import Image
import requests
from io import BytesIO
import discord


async def QRScanner(message: discord.Message, data: str):
    """Main Logic for actually handling the QR Codes. Actually quite simple."""
    response = requests.get(data)
    #await message.channel.send(message.content)
    #await message.channel.send(data)
    decodedImage = decode(Image.open(BytesIO(response.content)))
    await message.channel.send(str(decodedImage))
    AreWeThereYet = str(decodedImage[0])
    QRURL = AreWeThereYet.partition("data=b'")[2].partition("',")[0]
    TheRealQRURL = (f"`{QRURL}`")

    await message.channel.send(TheRealQRURL)

