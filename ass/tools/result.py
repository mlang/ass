from ass.oai import function


@function(help="Ask the model to return results to stdout.")
async def result(env, /, *, value: str):
    """Use this function to return a requested result, like a shell command.

    If you are asked to generate a specific result, like a command or a 
    document in a particular format, use this function to return the final result.

    This will be used to distinguish different text output types.
    Your normal output will be directed to the screen.
    """

    print(value)

    return "OK, we're done"
