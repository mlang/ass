from asyncio import Semaphore, create_subprocess_exec
from contextlib import asynccontextmanager
from glob import glob
from os import mkdir
from os.path import basename, splitext, expanduser, join, exists
from pathlib import Path
from uuid import uuid4

from asynctempfile import TemporaryDirectory, NamedTemporaryFile # type: ignore


_only_one = Semaphore(1)

async def play(items: list[bytes | Path]):
    async with TemporaryDirectory() as dir:
        files=[]
        for item in items:
            if isinstance(item, bytes):
                file = await NamedTemporaryFile(dir=dir, delete=False)
                await file.write(item)
                await file.close()
                files.append(file.name)
            elif isinstance(item, Path):
                files.append(str(item.resolve()))

        async with _only_one:
            await cat(files, "-f", "alsa", "default")


async def cat(files, *output_args):
    args = ["-loglevel", "error"]
    args.extend(arg for file in files for arg in ['-i', file])
    args.extend([
        "-filter_complex", f"concat=n={len(files)}:v=0:a=1[a]", "-map", "[a]"
    ])
    args.extend(output_args)
    ffmpeg = await create_subprocess_exec("ffmpeg", *args)
    await ffmpeg.wait()


async def start_recording(
    source=["-f", "alsa", "-channels", "4", "-i", "hw:CARD=sofhdadsp,DEV=7"],
    cache_dir="~/.cache/ass/recordings"
):
    cache_dir = expanduser(cache_dir)
    if not exists(cache_dir):
        mkdir(cache_dir)
    file = join(cache_dir, f'{uuid4()}.mp3')
    args = ['-loglevel', 'quiet']
    args.extend(source)
    args.extend(['-ac', '1', '-b:a', '128k', '-y', file])
    ffmpeg = await create_subprocess_exec('ffmpeg', *args)

    async def transcribe(transcriptions, model='whisper-1'):
        ffmpeg.terminate()
        with open(file, 'rb') as mp3:
            text = await transcriptions.create(
                file=mp3, model=model, response_format='text'
            )
            return text.strip()

    return transcribe


icons = {
    splitext(basename(file))[0]: Path(file)
    for file in glob('/usr/share/sounds/sound-icons/*.wav')
}
