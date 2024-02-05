from asyncio import gather
from contextlib import asynccontextmanager
from dataclasses import dataclass
from openai import AsyncOpenAI

@asynccontextmanager
async def new_assistant(openai: AsyncOpenAI, **kwargs):
    assistant = await openai.beta.assistants.create(**kwargs)
    try:
        yield assistant
    finally:
        await openai.beta.assistants.delete(assistant.id)

@asynccontextmanager
async def new_thread(openai: AsyncOpenAI, **kwargs):
    thread = await openai.beta.threads.create(**kwargs)
    try:
        yield thread
    finally:
        await openai.beta.threads.delete(thread.id)

@asynccontextmanager
async def new_files(openai: AsyncOpenAI, files):
    exceptions = []
    uploaded = []
    for item in await gather(
        *(openai.files.create(file=file, purpose='assistants') for file in files),
        return_exceptions=True
    ):
        if isinstance(item, BaseException):
            exceptions.append(item)
        else:
            uploaded.append(item)
    try:
        if exceptions:
            raise exceptions[0]
        yield uploaded
    finally:
        await gather(
            *(openai.files.delete(file.id) for file in uploaded)
        )


@dataclass(slots=True)
class Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0

    def __iadd__(self, other):
        self.prompt_tokens += other.prompt_tokens
        self.completion_tokens += other.completion_tokens
        return self
