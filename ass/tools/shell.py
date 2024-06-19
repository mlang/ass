from asyncio import create_subprocess_shell
from asyncio.subprocess import PIPE

from ass.ptutils import ConfirmDialog
from ass.oai import function


@function(help="""Give the model (supervised) access to the local Shell.""")
async def shell(env, /, *, command: str):
    """Execute a shell command (bash)."""

    if await env.show_dialog(ConfirmDialog("Run shell command?", command)):
        process = await create_subprocess_shell(command,
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
