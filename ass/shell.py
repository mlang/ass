from importlib import resources

import click

from ass.oai import tools_options

@click.command(help="Command-line generator for Bash")
@tools_options(exclude=['result', 'shell', 'dialogs'])
def bash(**spec):
    print("""# Bash integration
#
# To install, run the following command:
#
# eval "$(ass bash)"
#
# And bind the function to a sequence of your liking:
#
# bind -x '"\C-xa": ass-ask-bash'""")
    print()
    print(f'''ASS_ASK_BASH_INSTRUCTIONS="{_instructions("Bash")}"''')
    print(f'''ASS_ASK_BASH_TOOLS="{_to_args(spec)}"''')
    print(resources.read_text(__package__, "bash.sh"))


@click.command(help="Command-line generator for Zsh")
@tools_options(exclude=['result', 'shell', 'dialogs'])
def zsh(**spec):
    print("""# Zsh integration
#
# To install, run the following command:
#
# eval "$(ass zsh)"
#
# And bind the function to a sequence of your liking:
#
# bindkey '^xa' ass-ask-zsh""")
    print()
    print(f'''ASS_ASK_ZSH_INSTRUCTIONS="{_instructions("Zsh")}"''')
    print(f'''ASS_ASK_ZSH_TOOLS="{_to_args(spec)}"''')
    print(resources.read_text(__package__, "zsh.sh"))


def _instructions(shell: str) -> str:
    return f"""You are a {shell} command generator.
Whatever you are asked, you will always provide a shell command via the result function tool.
Everything else you say will be echoed to the users screen.
Only return the result via the result function, never display it
using markdown fencing.  Be brief with comments, don't waste the users time.
The shell command will be inserted into the users readline buffer for review
and potential submission to an interactive shell."""


def _to_args(spec: dict) -> str:
    return " ".join(
        f"--{name.replace('_', '-')}"
        for name, enabled in spec.items() if enabled
    )
