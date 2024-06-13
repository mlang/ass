from abc import abstractmethod
from importlib.util import spec_from_file_location, module_from_spec
import inspect
from os import path, walk
from typing import Any, Callable, Dict, Type
from typing_extensions import Annotated

from click import option
from openai.types.beta import (
    AssistantToolParam, CodeInterpreterToolParam, FunctionToolParam
)
from pydantic import create_model, BaseModel, ConfigDict


class FunctionModel(BaseModel):
    model_config = ConfigDict(frozen=True)

    @classmethod
    def function_tool_param(cls) -> FunctionToolParam:
        def filter_title(schema: dict) -> dict:
            return { k: (filter_title(v) if isinstance(v, dict) else v)
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

    @abstractmethod
    def __call__(self, *args):
        ...


def _to_model(func: Type[Callable[..., Any]]) -> Type[FunctionModel]:
    def __call__(self, *args):
        return func(*args, **self.model_dump())

    fields: Dict[str, Any] = {
        name: (
            param.annotation if param.annotation != param.empty else Any,
            param.default if param.default != param.empty else ...
        )
        for name, param in inspect.signature(func).parameters.items()
        if param.kind not in (inspect.Parameter.POSITIONAL_ONLY,)
    }

    return create_model(func.__name__,
        __base__=type('Model', (FunctionModel,), {'__call__': __call__}),
        __doc__=func.__doc__,
        **fields
    )


def function(*, help):
    def decorator(func):
        global _options, tools
        cls = _to_model(func)
        tool_call.add(cls)
        option_name = f"--{cls.__name__.replace('_', '-')}"
        _options.append(
            (
                cls.__name__,
                option(option_name, is_flag=True, default=False, help=help)
            )
        )
        tools[cls.__name__] = cls.function_tool_param()

        return func

    return decorator


def load_tools():
    for spec in (
        spec_from_file_location('plugin', path.join(root, file))
        for dir in (
            "/etc/ass/plugins/", path.expanduser("~/.config/ass/plugins/")
        )
        for root, dirs, files in walk(dir)
        for file in files if file.endswith('.py')
    ):
        spec.loader.exec_module(module_from_spec(spec))


tools: Dict[str, AssistantToolParam] = {
    'code_interpreter': CodeInterpreterToolParam(type='code_interpreter'),
}

_options = [
    ( "code_interpreter"
    , option("--code-interpreter", is_flag=True, default=False,
             help="Offer a code_interpreter to the assistant.")
    )
]


def tools_options(exclude=[]):
    def decorator(command):
        for name, flag in reversed(_options):
            if name not in exclude:
                command = flag(command)

        return command

    return decorator


class tool_call:
    models: Dict[str, Type[FunctionModel]] = {}

    @classmethod
    def add(cls, model: Type[FunctionModel]):
        cls.models[model.__name__] = model

    @classmethod
    def validate(cls, name: str, arguments: str):
        return cls.models[name].model_validate_json(arguments)

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    async def __call__(self, function):
        return await self.validate(function.name, function.arguments)(self)
