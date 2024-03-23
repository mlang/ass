from asyncio import Future, Semaphore
from typing import Any, Generator, Generic, TypeVar
from prompt_toolkit.application.current import get_app
from prompt_toolkit.completion import PathCompleter
from prompt_toolkit.layout.containers import Float, FloatContainer, HSplit
from prompt_toolkit.widgets import (
    Button, CheckboxList, Dialog, Label, RadioList, TextArea
)

T = TypeVar('T')
class ModalDialog(Dialog, Generic[T]):
    def __init__(self, **kwargs):
        self.future = Future()
        super().__init__(modal=True, **kwargs)
    def finish(self, value: T) -> None:
        self.future.set_result(value)
    def __await__(self) -> Generator[Any, None, T]:
        return self.future.__await__()


class ConfirmDialog(ModalDialog):
    def __init__(self, title="", text="", yes_label="Yes", no_label="No"):
        def accept_text(buffer):
            get_app().layout.focus(buttons[0])
            buffer.complete_state = None
            return True
        textarea = TextArea(text=text, multiline=True, read_only=True,
            accept_handler=accept_text
        )
        buttons = [
            Button(text=yes_label, handler=lambda: self.finish(True)),
            Button(text=no_label, handler=lambda: self.finish(False))
        ]
        super().__init__(title=title, body=textarea, buttons=buttons)


class TextInputDialog(ModalDialog):
    def __init__(self,
        title="", text="", ok_label="OK", cancel_label="Cancel", completer=None
    ):
        def accept_text(buffer):
            get_app().layout.focus(buttons[0])
            buffer.complete_state = None
            return True
        self.textarea = TextArea(
            multiline=False,
            completer=completer,
            accept_handler=accept_text
        )
        buttons = [
            Button(text=ok_label, handler=lambda: self.finish(self.textarea.text)),
            Button(text=cancel_label, handler=lambda: self.finish(None))
        ]
        super().__init__(
            title=title,
            body=HSplit([Label(text=text), self.textarea]),
            buttons=buttons
        )

class PathInputDialog(TextInputDialog):
    def __init__(self,
        title="", text="", only_directories=False, ok_label="OK", cancel_label="Cancel"
    ):
        super().__init__(title=title, text=text,
            ok_label=ok_label, cancel_label=cancel_label,
            completer=PathCompleter(only_directories=only_directories)
        )


class RadioListDialog(ModalDialog):
    def __init__(self, title="", text="", values=[],
                 ok_label="OK", cancel_label="Cancel"
    ):
        self.radiolist = RadioList(
            values=[(value, value) for value in values]
        )
        buttons = [
            Button(text=ok_label, handler=lambda: self.finish(self.radiolist.current_value)),
            Button(text=cancel_label, handler=lambda: self.finish(None))
        ]
        super().__init__(
            title=title,
            body=HSplit([Label(text=text), self.radiolist]),
            buttons=buttons
        )


class CheckboxListDialog(ModalDialog):
    def __init__(self, title="", text="", values=[],
                 ok_label="OK", cancel_label="Cancel"
    ):
        self.checkboxlist = CheckboxList(
            values=[(value, value) for value in values]
        )
        buttons = [
            Button(text=ok_label, handler=lambda: self.finish(self.checkboxlist.current_values)),
            Button(text=cancel_label, handler=lambda: self.finish(None))
        ]
        super().__init__(
            title=title,
            body=HSplit([Label(text=text), self.checkboxlist]),
            buttons=buttons
        )


there_can_be_only_one = Semaphore(1)

async def show_dialog(container: FloatContainer, dialog: ModalDialog[T]) -> T:
    floats = container.floats
    float_ = Float(content=dialog)
    async with there_can_be_only_one:
        floats.insert(0, float_)

        app = get_app()
        focused_before = app.layout.current_window
        app.layout.focus(dialog)
        app.invalidate()
        result = await dialog
        app.layout.focus(focused_before)

        floats.remove(float_)

        return result
