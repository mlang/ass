from abc import abstractmethod
from asyncio import Semaphore, gather, sleep
from contextlib import asynccontextmanager, AsyncExitStack
from dataclasses import dataclass
import hashlib
from importlib.util import spec_from_file_location, module_from_spec
import inspect
import json
import os
from pathlib import Path
import traceback
from typing import (Any, AsyncIterator, Awaitable, Callable, ClassVar, Dict,
                    List, Tuple, Type)

import click
from openai import AsyncOpenAI
from openai.resources.audio.speech import AsyncSpeech
from openai.resources.beta.assistants import AsyncAssistants
from openai.resources.beta.threads import AsyncThreads
from openai.resources.beta.threads.runs import AsyncRuns
from openai.resources.beta.vector_stores import AsyncVectorStores
from openai.types.beta import (
    AssistantToolParam, CodeInterpreterToolParam, FileSearchToolParam,
    FunctionToolParam
)
from openai.types.beta.assistant_stream_event import MessageDeltaEvent
from openai.types.beta.assistant_create_params import (
    AssistantCreateParams, ToolResources, ToolResourcesCodeInterpreter,
    ToolResourcesFileSearch
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
import pydantic


@asynccontextmanager
async def make_assistant(
    openai: AsyncOpenAI, files, /, *, instructions, model, **kwargs
) -> AsyncIterator[AssistantCreateParams]:
    tools = {k: v for k, v in _alltools().items() if k in kwargs if kwargs[k]}
    params = AssistantCreateParams(
        instructions=instructions,
        model=model,
        tools=tools.values()
    )

    async with AsyncExitStack() as stack:
        if files:
            tool_resources = ToolResources()
            remote_files = await stack.enter_async_context(
                temporary_files(openai, files)
            )
            if 'code_interpreter' in tools:
                tool_resources['code_interpreter'] = ToolResourcesCodeInterpreter(
                    file_ids=[file.id for file in remote_files]
                )
            if 'file_search' in tools:
                store = await stack.enter_async_context(
                    temporary_vector_store(openai.beta.vector_stores)
                )
                batch = await openai.beta.vector_stores.file_batches.create(
                    vector_store_id=store.id,
                    file_ids=[file.id for file in remote_files]
                )
                while batch.status == "in_progress":
                    await sleep(1)
                    batch = await openai.beta.vector_stores.file_batches.retrieve(
                        batch.id, vector_store_id=store.id
                    )

                tool_resources['file_search'] = ToolResourcesFileSearch(
                    vector_store_ids=[store.id]
                )

            params['tool_resources'] = tool_resources

        assistant = await stack.enter_async_context(
            temporary_assistant(openai.beta.assistants, **params)
        )

        yield assistant


@asynccontextmanager
async def temporary_assistant(assistants: AsyncAssistants, **kwargs):
    assistant = await assistants.create(**kwargs)
    try:
        yield assistant
    finally:
        await assistants.delete(assistant.id)


@asynccontextmanager
async def temporary_thread(threads: AsyncThreads, **kwargs):
    thread = await threads.create(**kwargs)
    try:
        yield thread
    finally:
        await threads.delete(thread.id)


@asynccontextmanager
async def temporary_vector_store(vector_stores: AsyncVectorStores, **kwargs):
    vector_store = await vector_stores.create(**kwargs)
    try:
        yield vector_store
    finally:
        await vector_stores.delete(vector_store.id)


@asynccontextmanager
async def temporary_files(openai: AsyncOpenAI, files):
    exceptions = []
    uploaded = []
    for item in await gather(
        *(openai.files.create(file=file, purpose='assistants')
          for file in files),
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


async def stream_a_run(runs: AsyncRuns, /, *,
    function_tool_args: List[Any] = [], **kwargs
):
    async def call_tool(
        tool_call: RequiredActionFunctionToolCall
    ) -> ToolOutput:
        return {
            'tool_call_id': tool_call.id,
            'output': await _call(tool_call.function, *function_tool_args)
        }

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
                        stream = await runs.submit_tool_outputs(stream=True,
                            thread_id=run.thread_id, run_id=run.id,
                            tool_outputs=await gather(
                                *map(call_tool, tool_calls)
                            )
                        )

    await stream.close()


def function(**kwargs):
    """Register an async def with keyword arguments as a function tool."""

    def decorator(func):
        _create_function_tool(func, **kwargs)

        return func

    return decorator


class FunctionTool(pydantic.BaseModel):
    """A base class for defining function tools."""

    @abstractmethod
    async def __call__(self, *args):
        ...

    _models: ClassVar[Dict[str, 'FunctionTool']] = {}
    _options: ClassVar[List[Tuple[str, Callable[[Any], Any]]]] = []

    @classmethod
    def __pydantic_init_subclass__(cls, /, *, help, default=False):
        FunctionTool._models[cls.__name__] = cls
        flag = click.option(f"--{cls.__name__.replace('_', '-')}",
            is_flag=True, default=default, help=help
        )
        FunctionTool._options.append((cls.__name__, flag))

    @classmethod
    def function_tool_param(cls) -> FunctionToolParam:
        def filter_title(schema: dict) -> dict:
            return {
                k: (filter_title(v) if isinstance(v, dict) else v)
                for k, v in schema.items()
                if not (k == 'title' and isinstance(v, str))
            }

        schema = filter_title(cls.model_json_schema())

        return {
            'type': 'function',
            'function': {
                'name': cls.__name__,
                'description': schema.pop('description'),
                'parameters': schema
            }
        }

    @classmethod
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__()

    model_config = pydantic.ConfigDict(frozen=True)


async def text_to_speech(speech: AsyncSpeech, text, *,
    model="tts-1-hd", voice="nova", speed=1.0, response_format="mp3",
    cache_dir="~/.cache/ass/openai/audio/speech",
    semaphore=Semaphore(1)
) -> Path:
    text = text.strip()
    hash = hashlib.sha3_512(text.encode('utf-8')).hexdigest()
    dir, basename = hash[:3], hash[3:]
    path = (
        Path(cache_dir).expanduser() / model / voice / str(speed) /
        dir / f"{basename}.{response_format}"
    )
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        async with semaphore:
            async with speech.with_streaming_response.create(input=text,
                model=model, voice=voice, speed=speed,
                response_format=response_format
            ) as response:
                await response.stream_to_file(path)

    return path


def tools_options(exclude=[]):
    """Add enablers for all registered tools to a command."""

    def decorator(command):
        for name, flag in reversed(_internaloptions + FunctionTool._options):
            if name not in exclude:
                command = flag(command)

        return command

    return decorator


class environment:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


def load_tools():
    for spec in (
        spec_from_file_location('plugin', os.path.join(root, file))
        for dir in (
            "/etc/ass/plugins/", os.path.expanduser("~/.config/ass/plugins/")
        )
        for root, dirs, files in os.walk(dir)
        for file in files if file.endswith('.py')
    ):
        spec.loader.exec_module(module_from_spec(spec))


async def _call(function: Function, *args: Any) -> str:
    """Call a function tool."""

    try:
        model = FunctionTool._models[function.name]
        result = await model.model_validate_json(function.arguments)(*args)

        if isinstance(result, pydantic.BaseModel):
            return result.model_dump_json()

        return json.dumps(result)

    except BaseException:
        return traceback.format_exc()


def _create_function_tool(
    func: Type[Callable[..., Awaitable[Any]]], **kwargs
) -> Type[FunctionTool]:
    def _or(value, default):
        return value if value != inspect.Parameter.empty else default

    fields: Dict[str, Any] = {
        param.name: (_or(param.annotation, Any), _or(param.default, ...))
        for param in inspect.signature(func).parameters.values()
        if param.kind == inspect.Parameter.KEYWORD_ONLY
    }

    async def __call__(self, *args):
        return await func(*args, **dict(self))

    impl = type(func.__name__+'Callable', (), {'__call__': __call__})

    return pydantic.create_model(func.__name__,
        __doc__=func.__doc__, __base__=(impl, FunctionTool),
        __cls_kwargs__=kwargs, **fields
    )


def _alltools():
    functiontools = {
        name: model.function_tool_param()
        for name, model in FunctionTool._models.items()
    }
    return {**_internaltools, **functiontools}


_internaltools: Dict[str, AssistantToolParam] = {
    'code_interpreter': CodeInterpreterToolParam(type='code_interpreter'),
    'file_search': FileSearchToolParam(type='file_search')
}

_internaloptions = [
    ("code_interpreter",
     click.option("--code-interpreter", is_flag=True, default=False,
                  help="""Offer a code_interpreter to the assistant.""")),
    ("file_search",
     click.option("--file-search", is_flag=True, default=False,
                  help="""Add provided files to a vector store."""))
]


@dataclass(slots=True)
class AUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0

    def __iadd__(self, other):
        self.prompt_tokens += other.prompt_tokens
        self.completion_tokens += other.completion_tokens
        return self
