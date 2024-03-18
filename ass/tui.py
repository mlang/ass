from asyncio import create_task, run
from dataclasses import dataclass, field
from functools import partial
import re
from typing import Optional
from click import command, option, argument, pass_obj, File
from openai import AsyncOpenAI
from prompt_toolkit.application import Application
from prompt_toolkit.application.current import get_app
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.document import Document
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.key_binding.bindings.focus import focus_next
from prompt_toolkit.layout.containers import (
    FloatContainer, FormattedTextControl, HSplit, VSplit, Window, WindowAlign
)
from prompt_toolkit.layout.layout import Layout
from prompt_toolkit.lexers import PygmentsLexer
from prompt_toolkit.styles import Style
from prompt_toolkit.widgets import (
    SearchToolbar, TextArea
)
from pygments.lexers.markup import MarkdownLexer

from ass.oai import new_assistant, new_thread, new_files, AUsage, MsgText, StatusChanged, UsageReport, stream_a_run
from ass.ptutils import show_dialog
from ass.tools import tools_options, tools, tool_call

@command(help="Interactively chat with an assistant")
@option("--instructions", show_default=True, default="You are a helpful assistant.")
@option("--model", default="gpt-4-0125-preview", show_default=True)
@tools_options()
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
    run(async_ui(client, spec, files, tui))


async def async_ui(client, spec, files, ui):
    async with new_files(client.openai, files) as files:
        spec.update({'file_ids': [file.id for file in files]})
        async with new_assistant(client.openai, **spec) as assistant:
            async with new_thread(client.openai) as thread:
                await ui(client, thread, assistant)

async def tui(client, thread, assistant):
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
            ('class:run', f"[{state.status if state.status else ''}]"),
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
            display = partial(add_text, output_field)
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


async def txrx(openai: AsyncOpenAI, thread, text, assistant, display, state, call_tool):
    await openai.beta.threads.messages.create(
        thread_id=thread.id, role='user', content=text
    )
    display(f"\n{text}\n")
    async for output in stream_a_run(openai, call_tool,
        await openai.beta.threads.runs.create(
            stream=True, thread_id=thread.id, assistant_id=assistant.id
        )
    ):
        match output:
            case MsgText(token=token):
                display(token)
            case StatusChanged(status=status):
                state.status = status
                get_app().invalidate()
            case UsageReport(usage=usage):
                state.usage += usage


def add_text(text_area: TextArea, text: str) -> None:
    text_area.document = Document(
        text=text_area.text + text,
        cursor_position=text_area.document.cursor_position
    )


@dataclass
class State:
    usage: AUsage = field(default_factory=AUsage)
    status: Optional[str] = None
