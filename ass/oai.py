from asyncio import gather
from contextlib import asynccontextmanager
from dataclasses import dataclass
import json
from typing import Any, Callable, Coroutine

from openai import AsyncOpenAI
from openai.resources.beta.assistants import AsyncAssistants
from openai.resources.beta.threads import AsyncThreads
from openai.resources.beta.threads.runs import AsyncRuns
from openai.types.beta.assistant_stream_event import MessageDeltaEvent
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

async def stream_a_run(
    runs: AsyncRuns, call: Callable[[Function], Coroutine[None, None, Any]],
    **kwargs
):
    async def call_tool(tool_call):
        match tool_call:
            case RequiredActionFunctionToolCall(id=id, function=function):
                return ToolOutput(
                    tool_call_id=id, output=json.dumps(await call(function))
                )

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
class AUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0

    def __iadd__(self, other):
        self.prompt_tokens += other.prompt_tokens
        self.completion_tokens += other.completion_tokens
        return self
