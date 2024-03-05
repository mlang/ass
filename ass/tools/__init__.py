from importlib.util import spec_from_file_location, module_from_spec
import json
from os import path, walk

from click import option


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


__all__ = ['function', 'load_tools', 'tools_options', 'tools', 'tool_call']

tools = dict(
    code_interpreter={'type': 'code_interpreter'},
    retrieval={'type': 'retrieval'}
)

options = [
    option("--code-interpreter", is_flag=True, default=False,
           help="Offer a code_interpreter to the assistant."),
    option("--retrieval", is_flag=True, default=False,
           help="Use retrieval to index provided files.")
]


def tools_options(command):
    for flag in reversed(options):
        command = flag(command)

    return command


models = {}

def function(option_help):
    def decorator(model):
        global models, options, tools
        models[model.__name__] = model
        option_name = f"--{model.__name__.replace('_', '-')}"
        options.append(
            option(option_name, is_flag=True, default=False, help=option_help)
        )
        parameters = model.model_json_schema()
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


async def tool_call(show_dialog, client, tool_call):
    async def call(func):
        try:
            function = models[func.name](**json.loads(func.arguments))
            return await function(show_dialog, client)
        except Exception as e:
            return repr(e)

    return {
        'tool_call_id': tool_call.id,
        'output': json.dumps(await call(tool_call.function))
    }
