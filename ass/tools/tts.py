from asyncio import gather, Semaphore
from typing import List, Literal
from typing_extensions import Annotated

from pydantic import BaseModel, Field

from ass.oai import text_to_speech
from ass.snd import play, icons
from ass.oai import function


class Text(BaseModel):
    voice: Literal["alloy", "echo", "fable", "onyx", "nova", "shimmer"] = "nova"
    speed: float = Field(1.25, ge=1.0, lt=2.0)
    text: str = Field(min_length=1, max_length=4096)


IconName = Literal[*sorted(icons.keys())] # type: ignore

class SoundIcon(BaseModel):
    sound: IconName # type: ignore

@function(help="Let the model use Text-To-Speech and SoundIcons.")
async def tts(env, /, *,
    clips: Annotated[List[Text | SoundIcon], Field(min_length=1)]
):
    """Render synthetic speech and/or sound icons.
    Use it when answering the user with plain text.
    Use SoundIcons if appropriate, for instance, to indicate list items or
    emphasise words.
    Notice that the length of text clips is limited to 4096.
    For better parallel processing, and to avoid hitting the length limit,
    partition at the paragraph boundary.
    """

    limit = Semaphore(7)
    async def get_path(segment):
        if isinstance(segment, Text):
            return await text_to_speech(env.client.openai.audio.speech,
                text=segment.text, model="tts-1", voice=segment.voice,
                speed=segment.speed, response_format="mp3",
                semaphore=limit
            )
        else:
            return icons[segment.sound]

    await play(await gather(*map(get_path, clips)))

    return f"Played {len(clips)} audio segments"
