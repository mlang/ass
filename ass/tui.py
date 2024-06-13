from asyncio import create_task, run
from dataclasses import dataclass, field
from functools import partial
import re
from typing import Optional
from click import command, option, argument, pass_obj, File
from openai import AsyncOpenAI
from openai.types.beta.threads import Run
from prompt_toolkit.application import Application
from prompt_toolkit.application.current import get_app
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.document import Document
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.key_binding.bindings.focus import focus_next
from prompt_toolkit.layout.containers import (
    Float, FloatContainer, FormattedTextControl, HSplit, VSplit, Window, WindowAlign
)
from prompt_toolkit.layout.layout import Layout
from prompt_toolkit.layout.menus import CompletionsMenu
from prompt_toolkit.lexers import PygmentsLexer
from prompt_toolkit.styles import Style
from prompt_toolkit.widgets import (
    SearchToolbar, TextArea
)
from pygments.lexers.markup import MarkdownLexer

from ass.oai import new_assistant, new_thread, assistant_params, stream_a_run, AUsage
from ass.ptutils import show_dialog
from ass.snd import start_recording
from ass.tools import tools_options, tool_call

@command(help="Interactively chat with an assistant")
@option("--instructions", show_default=True, default="You are a helpful assistant.")
@option("--model", default="gpt-4o-2024-05-13", show_default=True)
@tools_options()
@argument("files", nargs=-1, type=File('rb'))
@pass_obj
def chat(client, *, files, **spec):
    run(async_ui(client, spec, files, tui))


async def async_ui(client, spec, files, ui):
    async with client as client:
        async with assistant_params(client.openai, files, **spec) as params:
            async with new_assistant(client.openai.beta.assistants, **params) as assistant:
                async with new_thread(client.openai.beta.threads) as thread:
                    await ui(client, thread, assistant)

async def tui(client, thread, assistant):
    state = State()
    search_field = SearchToolbar()

    output_field = TextArea(
        style="class:output-field",
        text="",
        read_only=True,
        wrap_lines=True,
        lexer=PygmentsLexer(MarkdownLexer)
    )

    def words():
        return set(re.findall(r'\S+', output_field.text))

    input_field = TextArea(
        height=1,
        prompt="> ",
        completer=WordCompleter(words),
        auto_suggest=AutoSuggestFromHistory(),
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
        floats=[
            Float(
                xcursor=True,
                ycursor=True,
                content=CompletionsMenu(max_height=16, scroll_offset=1),
            )
        ]
    )

    exec_tool_call = tool_call(
        show_dialog=partial(show_dialog, container),
        client=client
    )
    display = partial(add_text, output_field)
    def accept(buffer):
        if buffer.text:
            create_task(
                txrx(client.openai, thread, buffer.text, assistant, display, state, exec_tool_call)
            )

    input_field.accept_handler = accept

    stop_recording = None
    def trigger_record(event):
        async def coroutine():
            nonlocal stop_recording
            if stop_recording:
                async with stop_recording() as mp3:
                    stop_recording = None
                    text = await client.openai.audio.transcriptions.create(
                        file=mp3, model='whisper-1', response_format='text'
                    )
                    await txrx(client.openai, thread, text.strip(), assistant, display, state, exec_tool_call)
            else:
                stop_recording = await start_recording()

        create_task(coroutine())


    kb = KeyBindings()

    kb.add("c-x", "o")(focus_next)
    kb.add("c-x", "c-c")(lambda event: event.app.exit())
    kb.add("c-x", "c-r")(trigger_record)

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
    threads = openai.beta.threads
    await threads.messages.create(
        thread_id=thread.id, role='user', content=text
    )
    display(f"\n{text}\n")
    first = True
    async for event in stream_a_run(threads.runs, call_tool,
        thread_id=thread.id, assistant_id=assistant.id
    ):
        match event:
            case str(token):
                display(token, sync=first)
                first = False
            case Run(status=status, usage=usage):
                state.status = status
                if status in ('completed', 'failed', 'cancelled', 'expired'):
                    state.usage += usage
                get_app().invalidate()


def add_text(text_area: TextArea, text: str, sync=False) -> None:
    text_area.document = Document(
        text=text_area.text + text,
        cursor_position=len(text_area.text) if sync else text_area.document.cursor_position
    )
    if sync:
        get_app().layout.focus(text_area)


@dataclass
class State:
    usage: AUsage = field(default_factory=AUsage)
    status: Optional[str] = None
