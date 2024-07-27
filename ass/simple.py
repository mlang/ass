from asyncio import run
import sys


from click import command, option, argument, pass_obj, File

from ass.oai import (
    make_assistant, temporary_thread, stream_a_run, tools_options, environment
)


@command(help="Ask a single question")
@option("--instructions",
    show_default=True,
    default="You are a helpful assistant."
)
@option("--model", default="gpt-4o-2024-05-13", show_default=True)
@option("--message-file", type=File('r'), default='-', show_default=True,
        help="File to read the question from.")
@tools_options(exclude=('dialogs', 'shell'))
@argument("files", nargs=-1, type=File('rb'))
@pass_obj
def ask(client, *, files, message_file, **spec):
    run(async_ui(client, spec, files, message_file.read()))


async def async_ui(client, spec, files, text):
    async with client as client:
        env = environment(client=client)
        async with make_assistant(client.openai, files, **spec) as assistant:
            threads = client.openai.beta.threads
            async with temporary_thread(threads) as thread:
                file = sys.stderr if 'result' in spec else sys.stdout
                eol = False
                await threads.messages.create(thread_id=thread.id, role='user',
                    content=text
                )
                async for event in stream_a_run(threads.runs,
                    function_tool_args=[env],
                    thread_id=thread.id, assistant_id=assistant.id
                ):
                    match event:
                        case str(token):
                            print(token, end='', file=file, flush=True)
                            eol = True
                if eol:
                    print(file=file)
