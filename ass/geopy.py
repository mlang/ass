from asyncio import TimeoutError
from contextlib import contextmanager
from ssl import SSLError

from geopy.exc import GeocoderServiceError, GeocoderTimedOut, GeopyError # type: ignore
from geopy.adapters import AdapterHTTPError, BaseAsyncAdapter # type: ignore


def httpx_adapter(http_client):
    class HttpxAdapter(BaseAsyncAdapter):
        """The adapter which uses `httpx` library."""

        def __init__(self, *, proxies, ssl_context):
            super().__init__(proxies=proxies, ssl_context=ssl_context)

            self.proxies = proxies
            self.ssl_context = ssl_context

        async def get_text(self, url, *, timeout, headers):
            with self._normalize_exceptions():
                response = await http_client.get(url, timeout=timeout, headers=headers)
                self._raise_for_status(response)
                return response.text

        async def get_json(self, url, *, timeout, headers):
            with self._normalize_exceptions():
                response = await http_client.get(url, timeout=timeout, headers=headers)
                self._raise_for_status(response)
                return response.json()

        def _raise_for_status(self, resp):
            if resp.is_error:
                raise AdapterHTTPError(
                    "Non-successful status code %s" % resp.status_code,
                    status_code=resp.status_code,
                    headers=resp.headers,
                    text=resp.text
                )

        @contextmanager
        def _normalize_exceptions(self):
            try:
                yield
            except (GeopyError, AdapterHTTPError, AssertionError):
                raise
            except Exception as error:
                message = str(error)
                if isinstance(error, TimeoutError):
                    raise GeocoderTimedOut("Service timed out")
                elif isinstance(error, SSLError):
                    if "timed out" in message:
                        raise GeocoderTimedOut("Service timed out")
                raise GeocoderServiceError(message)

    return HttpxAdapter
