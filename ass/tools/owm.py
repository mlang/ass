from pydantic import BaseModel, Field

from ass.tools import function


@function("Retrieve current weather for a particular location",
    "Give the model access to OpenWeatherMap."
)
class weather(BaseModel):
    location: str = Field(
        description="""Will be looked up using a geocoder."""
    )

    model_config = dict(
        json_schema_extra=dict(
            examples=[dict(location='Steyergasse, Graz, Austria')]
        )
    )

    async def __call__(self, show_dialog, client):
        return await client.owm.weather(
            await client.geocoder.geocode(self.location)
        )
