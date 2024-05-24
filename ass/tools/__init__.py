from abc import abstractmethod
from importlib.util import spec_from_file_location, module_from_spec
from os import path, walk
from typing import Dict


from click import option

from openai.types.beta import (
    AssistantToolParam, CodeInterpreterToolParam, FunctionToolParam
)
from pydantic import BaseModel, ConfigDict


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


class Function(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)

    @abstractmethod
    async def __call__(self, env):
        ...

    @classmethod
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__()

    @classmethod
    def __pydantic_init_subclass__(cls, /, help):
        global _options, tools
        tool_call.models[cls.__name__] = cls
        option_name = f"--{cls.__name__.replace('_', '-')}"
        _options.append(
            (
                cls.__name__,
                option(option_name, is_flag=True, default=False, help=help)
            )
        )
        tools[cls.__name__] = cls.function_tool_param()

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


class tool_call:
    models: Dict[str, Function] = {}

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    async def __call__(self, function):
        model = self.models[function.name].model_validate_json(
            function.arguments
        )
        return await model(self)
