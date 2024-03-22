from importlib.util import spec_from_file_location, module_from_spec
import json
from os import path, walk

from click import option

__all__ = ['function', 'load_tools', 'tools_options', 'tools', 'tool_call']


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


tools = dict(
    code_interpreter={'type': 'code_interpreter'},
    retrieval={'type': 'retrieval'}
)

options = [
    ( "code_interpreter"
    , option("--code-interpreter", is_flag=True, default=False,
             help="Offer a code_interpreter to the assistant.")
    ),
    ( "retrieval"
    , option("--retrieval", is_flag=True, default=False,
             help="Use retrieval to index provided files.")
    )
  
]


def tools_options(exclude=[]):
    def decorator(command):
        for name, flag in reversed(options):
            if name not in exclude:
                command = flag(command)

        return command

    return decorator


models = {}


def function(option_help):
    def decorator(model):
        global models, options, tools
        models[model.__name__] = model
        option_name = f"--{model.__name__.replace('_', '-')}"
        options.append(
            (
                model.__name__,
                option(option_name, is_flag=True, default=False, help=option_help)
            )
        )
        parameters = without_title(model.model_json_schema())
        description = parameters.pop('description')
        tools[model.__name__] = dict(
            type='function',
            function=dict(
                name=model.__name__,
                description=description,
                parameters=parameters
            )
        )
        return model

    return decorator


async def tool_call(show_dialog, client, function):
    try:
        model = models[function.name](**json.loads(function.arguments))
        return await model(show_dialog, client)
    except Exception as e:
        return repr(e)


def without_title(schema):
    return { k: (without_title(v) if isinstance(v, dict) else v)
        for k, v in schema.items() if not (k == 'title' and isinstance(v, str))
    }
