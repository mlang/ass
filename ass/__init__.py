from asyncio import run
from asyncio.subprocess import PIPE
import sys

from click import argument, group, option, pass_context, pass_obj, File
from geopy.geocoders import Nominatim # type: ignore
import httpx
from openai import AsyncOpenAI

from ass.geopy import httpx_adapter
from ass.owm import AsyncOpenWeatherMap
from ass.snd import play

from ass.tools import load_tools
import ass.tools.orf
import ass.tools.owm
import ass.tools.shell
import ass.tools.tts
load_tools()

from ass import tui
from ass import vision

@group()
@option("--openai-api-key")
@option("--openweathermap-api-key")
@pass_context
def cli(ctx, **kwargs):
    ctx.obj = clients(**kwargs)

cli.add_command(tui.chat)
cli.add_command(vision.describe_image)

@cli.command(help="Text-To-Speech")
@option("--model", default="tts-1-hd")
@option("--voice", default="nova")
@option("--speed", default=1.2)
@option("--format", default="mp3")
@argument("input", type=File("r"), default="-")
@pass_obj
def tts(client, model, voice, speed, format, input):
    run(atts(client.openai, model, voice, speed, format, input.read()))

async def atts(openai: AsyncOpenAI, model, voice, speed, format, input):
    response = await openai.audio.speech.create(
        input=input, model=model, voice=voice, speed=speed, response_format=format
    )
    bytes = await response.aread()
    if not sys.stdout.isatty():
        sys.stdout.buffer.write(bytes)
    else:
        await play([bytes])


@cli.command()
@argument("location")
@pass_obj
def owm(client, location):
    print(run(aowm(client, location)))

async def aowm(client, location):
    return await client.owm.weather(await client.geocoder.geocode(location))

class clients:
    def __init__(self, *, openai_api_key, openweathermap_api_key):
        self.http = httpx.AsyncClient()
        self.openai = AsyncOpenAI(
            api_key=openai_api_key, http_client=self.http
        )
        self.geocoder = Nominatim(
            user_agent=__package__,
            adapter_factory=httpx_adapter(self.http)
        )
        self.owm = AsyncOpenWeatherMap(
            api_key=openweathermap_api_key, http_client=self.http
        )
