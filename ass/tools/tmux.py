"""Basic tmux access."""

from abc import abstractmethod
from asyncio import create_subprocess_exec
from asyncio.subprocess import PIPE
from typing import Generic, Iterable, Literal, Optional, TypeVar

from pydantic import BaseModel, ConfigDict

from ass.tools import function


Name = TypeVar('Name')

class Command(BaseModel, Generic[Name]):
    name: Name

    @abstractmethod
    def args(self) -> Iterable[str]:
        pass

    model_config = ConfigDict(extra='forbid', frozen=True)


class capture_pane(Command[Literal['capture-pane']]):
    def args(self):
        return ['-p']


class list_buffers(Command[Literal['list-buffers']]):
    def args(self):
        return []


class list_sessions(Command[Literal['list-sessions']]):
    def args(self):
        return []


class list_windows(Command[Literal['list-windows']]):
    session: Optional[str] = None
    """Only list windows for a particular session."""

    def args(self):
        value = []

        if self.session:
            value.extend(['-t', self.session])

        return value


TmuxCommand = ( capture_pane
              | list_buffers
              | list_sessions
              | list_windows
              )


@function(help="Allow access to tmux.")
async def tmux(env, /, *, command: TmuxCommand):
    """Call a tmux subcommand."""

    tmux = await create_subprocess_exec('tmux', command.name, *command.args(),
        stdout=PIPE, stderr=PIPE
    )
    output, error = await tmux.communicate()
    return {
        'returncode': tmux.returncode,
        **({'output': output.decode()} if output else {}),
        **({'error': error.decode()} if error else {})
    }
