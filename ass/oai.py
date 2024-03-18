from asyncio import gather
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Callable, Coroutine

from openai import AsyncOpenAI, AsyncStream
from openai.types.beta import AssistantStreamEvent
from openai.types.beta.assistant_stream_event import (
    MessageDeltaEvent,
    ThreadMessageDelta,
    ThreadRunCancelled,
    ThreadRunCancelling,
    ThreadRunCompleted,
    ThreadRunCreated,
    ThreadRunExpired,
    ThreadRunFailed,
    ThreadRunInProgress,
    ThreadRunQueued,
    ThreadRunRequiresAction,
    ThreadRunStepDelta
)
from openai.types.beta.threads import (
    MessageDelta,
    TextDeltaBlock,
    TextDelta,
    Run
)
from openai.types.beta.threads.run_submit_tool_outputs_params import ToolOutput
from openai.types.beta.threads.run import (
    RequiredAction,
    RequiredActionFunctionToolCall,
    RequiredActionSubmitToolOutputs,
    Usage
)
from openai.types.beta.threads.runs import (
    CodeInterpreterToolCallDelta,
    RunStepDeltaEvent,
    RunStepDelta,
    ToolCallDeltaObject
)
from openai.types.beta.threads.runs.code_interpreter_logs import (
    CodeInterpreterLogs
)
from openai.types.beta.threads.runs.code_interpreter_tool_call_delta import (
    CodeInterpreter
)

from pydantic import BaseModel


async def stream_a_run(
    openai: AsyncOpenAI,
    call_tool: Callable[
        [RequiredActionFunctionToolCall],
        Coroutine[None, None, ToolOutput]
    ],
    events: AsyncStream[AssistantStreamEvent]
):
    while event := await anext(events, None):
        match event:
            case ThreadMessageDelta(
                data=MessageDeltaEvent(delta=MessageDelta(content=list(blocks)))
            ):
                for block in blocks:
                    match block:
                        case TextDeltaBlock(text=TextDelta(value=str(token))):
                            yield MsgText(token=token)

            case ThreadRunStepDelta(
                data=RunStepDeltaEvent(
                    delta=RunStepDelta(
                        step_details=ToolCallDeltaObject(
                            tool_calls=list(tool_calls)
                        )
                    )
                )
            ):
                for tool_call in tool_calls:
                    match tool_call:
                        case CodeInterpreterToolCallDelta(
                            code_interpreter=CodeInterpreter(
                                input=input, outputs=outputs
                            )
                        ):
                            if input:
                                yield CodeInterpreterInput(token=input)
                            if outputs:
                                for output in outputs:
                                    match output:
                                        case CodeInterpreterLogs(logs=str(token)):
                                            yield CodeInterpreterOutput(token=token)

            case ( ThreadRunCreated(data=run)
                 | ThreadRunQueued(data=run)
                 | ThreadRunInProgress(data=run)
                 ):
                yield StatusChanged(status=run.status)

            case ( ThreadRunCompleted(data=run)
                 | ThreadRunFailed(data=run)
                 | ThreadRunCancelling(data=run)
                 | ThreadRunCancelled(data=run)
                 | ThreadRunExpired(data=run)
                 ):
                yield StatusChanged(status=run.status)
                if run.usage:
                    yield UsageReport(usage=run.usage)

            case ThreadRunRequiresAction(
                data=Run(
                    required_action=RequiredAction(
                        submit_tool_outputs=RequiredActionSubmitToolOutputs(
                            tool_calls=tool_calls
                        )
                    )
                ) as run
            ):
                yield StatusChanged(status=run.status)
                await events.close()
                events = await openai.beta.threads.runs.submit_tool_outputs(
                    stream=True, thread_id=run.thread_id, run_id=run.id,
                    tool_outputs=await gather(*map(call_tool, tool_calls))
                )


class MsgText(BaseModel):
    token: str

class CodeInterpreterInput(BaseModel):
    token: str

class CodeInterpreterOutput(BaseModel):
    token: str

class StatusChanged(BaseModel):
    status: str

class UsageReport(BaseModel):
    usage: Usage


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
class AUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0

    def __iadd__(self, other):
        self.prompt_tokens += other.prompt_tokens
        self.completion_tokens += other.completion_tokens
        return self
