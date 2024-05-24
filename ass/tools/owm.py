from pydantic import Field

from ass.tools import Function


class weather(Function, help="Give the model access to OpenWeatherMap."):
    """Retrieve current weather for a particular location."""

    location: str = Field(
        description="""Will be looked up using a geocoder."""
    )

    model_config = dict(
        json_schema_extra=dict(
            examples=[dict(location='Steyergasse, Graz, Austria')]
        )
    )

    async def __call__(self, env):
        return await env.client.owm.weather(
            await env.client.geocoder.geocode(self.location)
        )
