from asyncio import create_task, gather, run, sleep
from dataclasses import dataclass, field
from functools import partial
import re
from typing import Optional
from click import command, option, argument, pass_obj, File
from openai import AsyncOpenAI
from openai.resources.beta.threads.runs import AsyncRuns
from prompt_toolkit.application import Application
from prompt_toolkit.application.current import get_app
from prompt_toolkit.completion import PathCompleter, WordCompleter
from prompt_toolkit.document import Document
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.key_binding.bindings.focus import focus_next
from prompt_toolkit.layout.containers import (
    Float, FloatContainer, FormattedTextControl, HSplit, VSplit, Window, WindowAlign
)
from prompt_toolkit.layout.layout import Layout
from prompt_toolkit.lexers import PygmentsLexer
from prompt_toolkit.styles import Style
from prompt_toolkit.widgets import (
    Button, Dialog, FormattedTextToolbar, SearchToolbar, TextArea
)
from pygments.lexers.markup import MarkdownLexer

from ass.oai import new_assistant, new_thread, new_files, Usage
from ass.ptutils import show_dialog, ConfirmDialog, CheckboxListDialog, TextInputDialog
from ass.tools import tools_options, tools, tool_call

@command(help="Interactively chat with an assistant")
@option("--instructions", show_default=True, default="You are a helpful assistant.")
@option("--model", default="gpt-4-0125-preview", show_default=True)
@tools_options
@argument("files", nargs=-1, type=File('rb'))
@pass_obj
def chat(client, *, files, **spec):
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
    run(tui(client, spec, files))


async def tui(client, spec, files):
    async with new_files(client.openai, files) as files:
        spec.update({'file_ids': [file.id for file in files]})
        async with new_assistant(client.openai, **spec) as assistant:
            async with new_thread(client.openai) as thread:
                await app(client, thread, assistant)

async def app(client, thread, assistant):
    state = State()
    search_field = SearchToolbar()

    output_field = TextArea(
        style="class:output-field",
        text="",
        read_only=True,
        lexer=PygmentsLexer(MarkdownLexer)
    )

    def words():
        return set(re.findall(r'\S+', output_field.text))

    input_field = TextArea(
        height=1,
        prompt="> ",
        completer=WordCompleter(words),
        style="class:input-field",
        multiline=False,
        wrap_lines=True,
        search_field=search_field,
    )

    def status_text():
        return [
            ('', '---'),
            ('class:run', f"[{state.run.status if state.run else ''}]"),
            ('', '---')
        ]
    def status_text_right():
        return [
            ('', '---'),
            ('class:tokens', f"{state.usage.prompt_tokens}|{state.usage.completion_tokens}"),
            ('', "---"),
        ]
    statusbar = VSplit([
        Window(FormattedTextControl(status_text), char='-'),
        Window(FormattedTextControl(status_text_right), char='-',
            align=WindowAlign.RIGHT
        )
    ], height=1)

    container = FloatContainer(
        content=HSplit([
            output_field,
            statusbar,
            input_field,
            search_field
        ]),
        floats=[]
    )

    exec_tool_call = partial(tool_call,
        partial(show_dialog, container),
        client
    )
    def accept(buffer):
        if buffer.text:
            def display(text):
                add_text(output_field, f"\n{text}")
            create_task(
                txrx(client.openai, thread, buffer.text, assistant, display, state, exec_tool_call)
            )

    input_field.accept_handler = accept

    kb = KeyBindings()

    kb.add("c-x", "o")(focus_next)
    kb.add("c-x", "c-c")(lambda event: event.app.exit())

    style = Style([
        ("output-field", "bg:#000000 #ffffff"),
        ("input-field", "bg:#000044 #ffffff"),
        ("line", "#004400"),
    ])

    return await Application(
        layout=Layout(container, focused_element=input_field),
        key_bindings=kb,
        style=style,
        mouse_support=True,
        full_screen=True,
    ).run_async()


async def txrx(openai: AsyncOpenAI, thread, text, assistant, display, state, exec_tool_call):
    message = await openai.beta.threads.messages.create(
        thread_id=thread.id, role='user', content=text
    )
    display(text)
    state.run = await openai.beta.threads.runs.create(
        thread_id=thread.id, assistant_id=assistant.id
    )
    get_app().invalidate()
    while state.run.status in ('queued', 'in_progress'):
        await sleep(1)
        state.run = await openai.beta.threads.runs.retrieve(
            run_id=state.run.id, thread_id=thread.id
        )
        get_app().invalidate()
        if state.run.status == 'requires_action' and state.run.required_action is not None:
            state.run = await openai.beta.threads.runs.submit_tool_outputs(
                thread_id=thread.id, run_id=state.run.id,
                tool_outputs=await gather(*map(
                    exec_tool_call,
                    state.run.required_action.submit_tool_outputs.tool_calls
                ))
            )
            get_app().invalidate()

    state.usage += state.run.usage
    
    messages = await openai.beta.threads.messages.list(
        thread_id=thread.id, before=message.id
    )
    for msg in reversed(messages.data):
        display("".join(
            part.text.value for part in msg.content if part.type == 'text'
        ))


def add_text(text_area: TextArea, text: str) -> None:
    text_area.document = Document(
        text=text_area.text + text,
        cursor_position=text_area.document.cursor_position
    )


@dataclass
class State:
    usage: Usage = field(default_factory=Usage)
    run: Optional[AsyncRuns] = None
