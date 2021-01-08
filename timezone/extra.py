import asyncio
import discord
import datetime
import pytz
from redbot.core import commands, Config, checks
from typing import Union

ZERO = datetime.timedelta(0, 0, 0)

def isdigit(string : str) -> bool: # Python's str.isdigit() doesn't accept negative numbers.
    try:
        int(string)
        return True
    except ValueError:
        return False

class TimeZoneConverter(commands.Converter):
    async def convert(self, ctx, arg : str):
        if isdigit(arg):
            arg = int(arg)
            if abs(arg) <= 12:
                result = datetime.timezone(datetime.timedelta(hours=arg))
            else: raise commands.BadArgument("Offset must be within +/- 12 Hours from UTC")
        else:
            try:
                tz = pytz.timezone(arg)
                UTC = datetime.datetime.utcnow()
                result = datetime.timezone(tz.utcoffset(datetime.datetime.utcnow()))
            except pytz.exceptions.UnknownTimeZoneError:
                result = None

        if result is None:
            raise commands.BadArgument("Invalid Timezone")
        return result

def is_dst(timezone : pytz.timezone):
    tz = timezone
    UTC = datetime.datetime.utcnow()
    dt = UTC + tz.utcoffset(UTC)
    print(tz.dst(dt))
    return tz.dst(dt) != ZERO
