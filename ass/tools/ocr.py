from asyncio import create_subprocess_exec
from asyncio.subprocess import PIPE

from pydantic import HttpUrl

from ass.oai import function


@function(help="Allow the model to fetch images and run local OCR on them.")
async def ocr(env, /, *, url: HttpUrl):
    """Downloads an image and performs OCR on it, returning a string."""

    response = await env.client.http.get(str(url))
    response.raise_for_status()
    return await tesseract(response.content)


async def tesseract(source: bytes) -> str:
    tesseract = await create_subprocess_exec('tesseract', 'stdin', 'stdout',
        stdin=PIPE, stdout=PIPE, stderr=PIPE
    )
    output, error = await tesseract.communicate(input=source)
    if tesseract.returncode:
        raise RuntimeError(
            f"Tesseract-OCR Error ({tesseract.returncode}): {error.decode().strip()}"
        )
    return output.decode()
