from asyncio import gather, Semaphore
from typing import List, Literal

from pydantic import BaseModel, Field

from ass.oai import text_to_speech
from ass.snd import play, icons
from ass.tools import tool, Function


class Text(BaseModel):
    voice: Literal["alloy", "echo", "fable", "onyx", "nova", "shimmer"] = "nova"
    speed: float = Field(1.25, ge=1.0, lt=2.0)
    text: str = Field(min_length=1, max_length=4096)


IconName = Literal[*sorted(icons.keys())] # type: ignore

class SoundIcon(BaseModel):
    sound: IconName # type: ignore

@tool("Let the model use Text-To-Speech and SoundIcons.")
class tts(Function):
    """Render synthetic speech and/or sound icons.
    Use it when answering the user with plain text.
    Use SoundIcons if appropriate, for instance, to indicate list items or
    emphasise words.
    Notice that the length of text clips is limited to 4096.
    For better parallel processing, and to avoid hitting the length limit,
    partition at the paragraph boundary.
    """

    clips: List[Text | SoundIcon] = Field(min_length=1)

    async def __call__(self, env):
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

        await play(await gather(*map(get_path, self.clips)))

        return f"Played {len(self.clips)} audio segments"
