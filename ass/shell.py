from importlib import resources

import click

@click.command(help="Command-line generator for Bash")
def bash():
    print(resources.read_text(__package__, "bash.sh"))
