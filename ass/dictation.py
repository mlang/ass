from asyncio import gather, run
from functools import partial

from click import argument, command, option, pass_obj, File

from ass.snd import start_recording


@command(help="Speech-To-Text")
@option("--model", default="whisper-1", show_default=True)
@option("--language")
@option("--prompt")
@argument("files", nargs=-1, type=File('rb'))
@pass_obj
def stt(client, *, model, language, prompt, files):
    run(
        astt(
            client.openai.audio.transcriptions,
            model, language, prompt, files
        )
    )


async def astt(transcriptions, model, language, prompt, files):
    totext = partial(transcribe, transcriptions, model, language, prompt)
    if not files:
        stop_recording = await start_recording()
        input("Recording, press enter to stop...")
        async with stop_recording() as mp3:
            print(await totext(mp3))
    else:
        for text in await gather(*map(totext, files)):
            print(text)


async def transcribe(transcriptions, model, language, prompt, file):
    text = await transcriptions.create(
        file=file,
        model=model, language=language, prompt=prompt, response_format='text'
    )
    return text.strip()
