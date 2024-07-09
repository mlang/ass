"""OpenWeatherMap API client"""
import os
import httpx


class AsyncOpenWeatherMap:
    WEATHER_URL = "https://api.openweathermap.org/data/2.5/weather"

    def __init__(self, api_key=None, http_client=None):
        self.api_key = api_key or os.environ.get('OPENWEATHERMAP_API_KEY')
        if self.api_key is None:
            raise RuntimeError("Missing OpenWeatherMap API Key")
        self.http = http_client or httpx.AsyncClient()

    async def weather(self, location):
        params = dict(
            lat=location.latitude, lon=location.longitude,
            units='metric', appid=self.api_key
        )
        response = await self.http.get(self.WEATHER_URL, params=params)
        return response.json()
