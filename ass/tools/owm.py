from typing_extensions import Annotated

from pydantic import Field

from ass.oai import function


Location = Annotated[str,
    Field(
        description="""Will be looked up using a geocoder.""",
        example='Steyergasse, Graz, Austria'
    )
]

@function(help="Give the model access to OpenWeatherMap.")
async def weather(env, /, *, location: Location):
    """Retrieve current weather for a particular location."""

    return await env.client.owm.weather(
        await env.client.geocoder.geocode(location)
    )
