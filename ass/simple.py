from asyncio import run
from functools import partial

from click import command, option, argument, pass_obj, File

from ass.oai import new_assistant, new_thread, new_files, create_and_handle_required_actions
from ass.tools import tools_options, tools, tool_call


@command(help="Ask a single question")
@option("--instructions", show_default=True, default="You are a helpful assistant.")
@option("--model", default="gpt-4-0125-preview", show_default=True)
@option("--message-file", type=File('r'), default='-', show_default=True,
        help="File to read the question from.")
@tools_options(exclude=('dialogs', 'shell'))
@argument("files", nargs=-1, type=File('rb'))
@pass_obj
def ask(client, *, files, message_file, **spec):
    def fix_spec():
        nonlocal spec
        result = []
        for name in tools.keys():
            if name in spec:
                if spec[name]:
                    result.append(tools[name])
                del spec[name]
        return result
    spec['tools'] = fix_spec()
    run(async_ui(client, spec, files, partial(cli, message_file.read())))


async def async_ui(client, spec, files, ui):
    async with new_files(client.openai, files) as files:
        spec.update({'file_ids': [file.id for file in files]})
        async with new_assistant(client.openai.beta.assistants, **spec) as assistant:
            async with new_thread(client.openai.beta.threads) as thread:
                await ui(client, thread, assistant)

async def cli(text, client, thread, assistant):
    call_tool = partial(tool_call, None, client)
    threads = client.openai.beta.threads
    await threads.messages.create(
        thread_id=thread.id, role='user', content=text
    )
    async for event in create_and_handle_required_actions(
        threads.runs, call_tool, thread_id=thread.id, assistant_id=assistant.id
    ):
        match event:
            case str(token):
                print(token, end='', flush=True)
    print()
