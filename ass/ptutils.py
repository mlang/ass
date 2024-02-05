from asyncio import Future, Semaphore
from typing import Any, Generator, Generic, TypeVar
from prompt_toolkit.application.current import get_app
from prompt_toolkit.layout.containers import Float, FloatContainer
from prompt_toolkit.widgets import Button, Dialog, TextArea

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
    def __init__(self, title="", text=""):
        def accept_text(buffer):
            get_app().layout.focus(buttons[0])
            buffer.complete_state = None
            return True
        text_area = TextArea(text=text, multiline=True, read_only=True,
            accept_handler=accept_text
        )
        buttons = [
            Button(text="Allow", handler=lambda: self.finish(True)),
            Button(text="Deny", handler=lambda: self.finish(False))
        ]
        super().__init__(title=title, body=text_area, buttons=buttons)


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
