from asyncio import create_subprocess_shell
from asyncio.subprocess import PIPE

from ass.ptutils import ConfirmDialog
from ass.tools import tool, Function


@tool("Give the model (supervised) access to the local Shell.")
class shell(Function):
    """Execute a shell command (bash)."""

    command: str

    async def __call__(self, env):
        if await env.show_dialog(
            ConfirmDialog("Run shell command?", self.command)
        ):
            process = await create_subprocess_shell(self.command,
                stdout=PIPE, stderr=PIPE
            )
            stdout, stderr = await process.communicate()
            return {
                'returncode': process.returncode,
                **({'stdout': stdout.decode()} if stdout else {}),
                **({'stderr': stderr.decode()} if stderr else {})
            }
        else:
            return "User declined to run command"
