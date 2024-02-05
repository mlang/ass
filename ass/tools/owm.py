from pydantic import BaseModel

from ass.tools import function


@function("Retrieve current weather for a particular location", "Give the model access to OpenWeatherMap.")
class weather(BaseModel):
    location: str
    """Will be looked up using a geocoder"""

    async def __call__(self, show_dialog, client):
        return await client.owm.weather(
            await client.geocoder.geocode(self.location)
        )
