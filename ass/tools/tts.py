from asyncio import gather
from itertools import islice
from typing import List, Literal

from pydantic import BaseModel, Field

from ass.snd import play, icons
from ass.tools import function


class Text(BaseModel):
    voice: Literal["alloy", "echo", "fable", "onyx", "nova", "shimmer"] = "nova"
    speed: float = Field(1.0, ge=1.0, lt=2.0)
    text: str = Field(min_length=1, max_length=4096)

def batched(iterable, n):
    if n < 1:
        raise ValueError('n must be at least one')
    it = iter(iterable)
    while batch := tuple(islice(it, n)):
        yield batch

IconName = Literal[*sorted(icons.keys())] # type: ignore

class SoundIcon(BaseModel):
    name: IconName # type: ignore

@function(
    """Render synthetic speech and/or sound icons.
    Use it when answering the user with plain text.
    Use SoundIcons if appropriate, for instance, to indicate list items or
    emphasise words. Never use it to read code, use normal messages for
    code and/or other data. Never call this function more then once
    per tool call, since that would result in several clips being played at
    once. Audio output has been tested and is working properly.
    """,
    "Let the model use Text-To-Speech and SoundIcons."
)
class tts(BaseModel):
    clips: List[Text | SoundIcon] = Field(min_length=1)

    async def __call__(self, show_dialog, client):
        async def get(segment):
            if isinstance(segment, Text):
                response = await client.openai.audio.speech.create(
                    input=segment.text,
                    model="tts-1-hd",
                    voice=segment.voice,
                    speed=segment.speed,
                    response_format="mp3"
                )
                return await response.aread()
            else:
                return icons[segment.name]

        result = []
        for batch in batched((get(clip) for clip in self.clips), n=3):
            result.extend(await gather(*batch))

        await play(result)

        return f"Played {len(result)} audio segments"
