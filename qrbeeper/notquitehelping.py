from pyzbar.pyzbar import decode
from PIL import Image
import aiohttp
import asyncio
from io import BytesIO


async def QRScanner(data: str):
    """Main Logic for actually handling the QR Codes. Actually quite simple."""

    async with aiohttp.ClientSession() as sesh:
        async with sesh.get(data) as resp:
            try:
                decodedImage = decode(Image.open(BytesIO(resp.content)))
                AreWeThereYet = str(decodedImage[0])
                QRURL = AreWeThereYet.partition("data=b'")[2].partition("',")[0]
                return QRURL
            except:
                return "Error"

