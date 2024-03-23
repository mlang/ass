from asyncio import gather, Semaphore
from typing import List, Literal

from pydantic import BaseModel, Field

from ass.oai import text_to_speech
from ass.snd import play, icons
from ass.tools import function


class Text(BaseModel):
    voice: Literal["alloy", "echo", "fable", "onyx", "nova", "shimmer"] = "nova"
    speed: float = Field(1.0, ge=1.0, lt=2.0)
    text: str = Field(min_length=1, max_length=4096)


IconName = Literal[*sorted(icons.keys())] # type: ignore

class SoundIcon(BaseModel):
    name: IconName # type: ignore

@function("Let the model use Text-To-Speech and SoundIcons.")
class tts(BaseModel):
    """Render synthetic speech and/or sound icons.
    Use it when answering the user with plain text.
    Use SoundIcons if appropriate, for instance, to indicate list items or
    emphasise words. Never use it to read code, use normal messages for
    code and/or other data.
    """

    clips: List[Text | SoundIcon] = Field(min_length=1)

    async def __call__(self, show_dialog, client):
        limit = Semaphore(3)
        async def get_path(segment):
            if isinstance(segment, Text):
                return await text_to_speech(client.openai.audio.speech,
                    text=segment.text, model="tts-1-hd", voice=segment.voice,
                    speed=segment.speed, response_format="mp3",
                    semaphore=limit
                )
            else:
                return icons[segment.name]

        await play(await gather(*map(get_path, self.clips)))

        return f"Played {len(self.clips)} audio segments"
