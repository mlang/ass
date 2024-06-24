from asyncio import create_subprocess_exec
from asyncio.subprocess import DEVNULL, PIPE

from ass.oai import function


@function(help="""Allow the model to evaluate Emacs Lisp expressions (unsandboxed).""")
async def emacs_eval(env, /, *, expr: str):
    """Evaluate an Emacs Lisp expression in the currently running Emacs instance."""

    return await eval(expr)


async def eval(expr: str) -> str:
    emacsclient = await create_subprocess_exec('emacsclient', '--eval', expr,
        stdin=DEVNULL, stdout=PIPE, stderr=PIPE
    )
    output, error = await emacsclient.communicate()
    if emacsclient.returncode:
        raise RuntimeError(
            f"EmacsClient Error ({emacsclient.returncode}): {error.decode().strip()}"
        )
    return output.decode()
