from asyncio import Semaphore, create_subprocess_exec
from glob import glob
from os.path import basename, splitext
from pathlib import Path

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


icons = {
    splitext(basename(file))[0]: Path(file)
    for file in glob('/usr/share/sounds/sound-icons/*.wav')
}
