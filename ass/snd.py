"""Simple Ffmpeg-based sound I/O layer."""

from asyncio import Semaphore, create_subprocess_exec
from asyncio.subprocess import DEVNULL
from contextlib import asynccontextmanager
from glob import glob
from os import mkdir
from os.path import basename, splitext, expanduser, join, exists
from pathlib import Path
from uuid import uuid4

from asynctempfile import TemporaryDirectory, NamedTemporaryFile  # type: ignore


_only_one = Semaphore(1)


async def play(items: list[bytes | Path]):
    async with TemporaryDirectory() as dir:
        files = []
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
    filename = join(cache_dir, f'{uuid4()}.mp3')
    args = ['-loglevel', 'quiet']
    args.extend(source)
    args.extend(['-ac', '1', '-b:a', '128k', '-y', filename])
    ffmpeg = await create_subprocess_exec('ffmpeg', *args, stdin=DEVNULL)

    @asynccontextmanager
    async def stop_recording():
        ffmpeg.terminate()
        with open(filename, 'rb') as file:
            yield file

    return stop_recording


icons = {
    splitext(basename(file))[0]: Path(file)
    for file in glob('/usr/share/sounds/sound-icons/*.wav')
}
