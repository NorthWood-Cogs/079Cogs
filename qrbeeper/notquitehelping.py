from pyzbar.pyzbar import decode
from PIL import Image
import aiohttp
import asyncio
from io import BytesIO
import discord


async def QRScanner(message: discord.Message, data: str):
    """Main Logic for actually handling the QR Codes. Actually quite simple."""

    async with aiohttp.ClientSession() as sesh:
        async with sesh.get(data) as resp:
            await message.channel.send(message.content)
            await message.channel.send(data)
            decodedImage = decode(Image.open(BytesIO(resp.content)))
            AreWeThereYet = str(decodedImage[0])
            QRURL = AreWeThereYet.partition("data=b'")[2].partition("',")[0]

            await message.channel.send(QRURL)

