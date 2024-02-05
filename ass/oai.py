from asyncio import Semaphore, gather, sleep
from contextlib import asynccontextmanager
from dataclasses import dataclass
from hashlib import sha3_512
import json
from pathlib import Path
from traceback import format_exc
from typing import Any, AsyncIterator, Callable, Coroutine

from openai import AsyncOpenAI
from openai.resources.audio.speech import AsyncSpeech
from openai.resources.beta.assistants import AsyncAssistants
from openai.resources.beta.threads import AsyncThreads
from openai.resources.beta.threads.runs import AsyncRuns
from openai.resources.beta.vector_stores import AsyncVectorStores
from openai.types.beta import FileSearchToolParam
from openai.types.beta.assistant_stream_event import MessageDeltaEvent
from openai.types.beta.assistant_create_params import (
    AssistantCreateParams, ToolResources, ToolResourcesFileSearch
)
from openai.types.beta.threads import (
    MessageDelta, TextDeltaBlock, TextDelta, Run
)
from openai.types.beta.threads.run_submit_tool_outputs_params import ToolOutput
from openai.types.beta.threads.run import (
    RequiredAction,
    RequiredActionFunctionToolCall,
    RequiredActionSubmitToolOutputs,
)
from openai.types.beta.threads.required_action_function_tool_call import (
    Function
)
from ass.tools import tools


async def stream_a_run(
    runs: AsyncRuns, call: Callable[[Function], Coroutine[None, None, Any]],
    **kwargs
):
    async def call_tool(tool_call):
        match tool_call:
            case RequiredActionFunctionToolCall(id=id, function=function):
                try:
                    output = json.dumps(await call(function))
                except BaseException:
                    output = format_exc()
                return ToolOutput(tool_call_id=id, output=output)

    stream = await runs.create(stream=True, **kwargs)
    while event := await anext(stream, None):
        yield event
        match event.data:
            case MessageDeltaEvent(delta=MessageDelta(content=list(blocks))):
                for block in blocks:
                    match block:
                        case TextDeltaBlock(text=TextDelta(value=str(token))):
                            yield token

            case Run() as run:
                yield run
                match run.required_action:
                    case RequiredAction(
                        submit_tool_outputs=RequiredActionSubmitToolOutputs(
                            tool_calls=tool_calls
                        )
                    ):
                        await stream.close()
                        stream = await runs.submit_tool_outputs(
                            stream=True, thread_id=run.thread_id, run_id=run.id,
                            tool_outputs=await gather(
                                *map(call_tool, tool_calls)
                            )
                        )

    await stream.close()


@asynccontextmanager
async def new_assistant(assistants: AsyncAssistants, **kwargs):
    assistant = await assistants.create(**kwargs)
    try:
        yield assistant
    finally:
        await assistants.delete(assistant.id)

@asynccontextmanager
async def new_thread(threads: AsyncThreads, **kwargs):
    thread = await threads.create(**kwargs)
    try:
        yield thread
    finally:
        await threads.delete(thread.id)


@asynccontextmanager
async def new_vector_store(vector_stores: AsyncVectorStores, **kwargs):
    vector_store = await vector_stores.create(**kwargs)
    try:
        yield vector_store
    finally:
        await vector_stores.delete(vector_store.id)


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


@asynccontextmanager
async def assistant_params(
    openai: AsyncOpenAI, files, **kwargs
) -> AsyncIterator[AssistantCreateParams]:
    params = AssistantCreateParams(
        instructions=kwargs['instructions'],
        model=kwargs['model'],
        tools=[tools[tool]
            for tool in tools.keys() if tool in kwargs if kwargs[tool]
        ]
    )

    if not files:
        yield params
        return

    async with new_files(openai, files) as remote_files:
        async with new_vector_store(openai.beta.vector_stores) as store:
            batch = await openai.beta.vector_stores.file_batches.create(
                vector_store_id=store.id,
                file_ids=[file.id for file in remote_files]
            )
            while batch.status == "in_progress":
                await sleep(1)
                batch = await openai.beta.vector_stores.file_batches.retrieve(
                    batch.id, vector_store_id=store.id
                )

            params['tools'].append(FileSearchToolParam(type='file_search')) # type: ignore
            params['tool_resources'] = ToolResources(
                file_search=ToolResourcesFileSearch(
                    vector_store_ids=[store.id]
                )
            )

            yield params


async def text_to_speech(speech: AsyncSpeech, text, *,
    model="tts-1-hd", voice="nova", speed=1.0, response_format="mp3",
    cache_dir="~/.cache/ass/openai/audio/speech",
    semaphore=Semaphore(1)
) -> Path:
    text = text.strip()
    hash = sha3_512(text.encode('utf-8')).hexdigest()
    dir, basename = hash[:3], hash[3:]
    path = (
        Path(cache_dir).expanduser() / model / voice / str(speed) /
        dir / f"{basename}.{response_format}"
    )
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        async with semaphore:
            async with speech.with_streaming_response.create(
                input=text, model=model, voice=voice, speed=speed, response_format=response_format
            ) as response:
                await response.stream_to_file(path)

    return path


@dataclass(slots=True)
class AUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0

    def __iadd__(self, other):
        self.prompt_tokens += other.prompt_tokens
        self.completion_tokens += other.completion_tokens
        return self
