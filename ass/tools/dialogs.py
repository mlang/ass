from typing import List, Literal
from typing_extensions import Annotated

from pydantic import BaseModel, ConfigDict, Field

import ass.ptutils as ptdialogs
from ass.tools import function

class DialogModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

class ConfirmDialog(DialogModel):
    """A message dialog which asks the user to either confirm or deny.
    Return type is a boolean value.
    """

    type: Literal['ConfirmDialog']
    title: str = Field(max_length=64,
        description="The title of the dialog box."
    )
    text: str = Field(
        description="The message text to display in the dialog box."
    )
    yes_label: str = Field("Yes",
        description="The label of the confirmation button."
    )
    no_label: str = Field("No",
        description="The label of the button which cancels the dialog."
    )

class TextInputDialog(DialogModel):
    """A dialog which allows the user to enter a string.
    Returns either a string or null, which indicates the user cancelled
    the dialog.
    """

    type: Literal['TextInputDialog']
    title: str = Field(max_length=64)
    text: str = Field(
        description="A message displayed above the text entry field."
    )
    ok_label: str = "OK"
    cancel_label: str = "Cancel"


class PathInputDialog(DialogModel):
    """A dialog which asks the user to enter a filename.
    Returns either a string or null, which indicates the user cancelled
    the dialog.
    """

    type: Literal['PathInputDialog']
    title: str = Field(max_length=64)
    text: str = Field(
        description="A message displayed above the text entry field."
    )
    only_directories: bool = Field(False,
        description="If True, filename completion will only offer directories."
    )
    ok_label: str = "OK"
    cancel_label: str = "Cancel"


class RadioListDialog(DialogModel):
    """A radio button list dialog.
    Returns the selected item, or null when the user cancelled the dialog.
    """

    type: Literal['RadioListDialog']
    title: str = Field(max_length=64)
    text: str = Field(
        description="Text displayed above of the radio button list."
    )
    values: List[str] = Field(
        min_length=2,
        max_length=32,
        description="The list items."
    )
    ok_label: str = Field("OK", min_length=1, max_length=20)
    cancel_label: str = Field("Cancel", min_length=1, max_length=20)


class CheckboxListDialog(DialogModel):
    """A checkbox list dialog.
    Returns a list of all selected items,
    or null when the user cancelled the dialog.
    """
    type: Literal['CheckboxListDialog']
    title: str = Field(max_length=64)
    text: str = Field(description="Text displayed above of the checkbox list.")
    values: List[str] = Field(
        min_length=2,
        max_length=32,
        description="The checkbox items."
    )
    ok_label: str = Field("OK", min_length=1, max_length=20)
    cancel_label: str = Field("Cancel", min_length=1, max_length=20)


Questions = Annotated[
    List[ ConfirmDialog
        | RadioListDialog
        | CheckboxListDialog
        | TextInputDialog
        | PathInputDialog
        ],
    Field(
        description="""List of modal dialogs to pop up in sequence. """
                    """Returns a list of the results.""",
        min_length=1, max_length=99,
        discriminator='type',
        example=[
            dict(type='ConfirmDialog',
                 title="Ready?",
                 text="Are you ready to begin?",
                 yes_label="Sure", no_label="No, thanks"
            ),
            dict(type='TextInputDialog',
                 title="Your name",
                 text="Please enter your name."
            ),
            dict(type='PathInputDialog',
                 title="Enter a filename",
                 text="Please enter a filename."
            ),
            dict(type='RadioListDialog',
                 title="Gender",
                 text="Please select your biological gender.",
                 values=["Female", "Male"]
            ),
            dict(type='CheckboxListDialog',
                title="Favourite colours",
                text="What colours do you like?",
                values=["Blue", "Green", "Red", "Yellow"]
            )
        ]
    )
]

@function(help="Allow the model to pop up dialog boxes.")
async def dialogs(env, /, *, questions: Questions):
    """Execute a sequence of modal dialogs.
    Use this to inquire information from the user.
    Always use it when asked to generate a quiz.
    Make sure to customize the button labels according to the conversation language.
    """

    def model(question):
        args = question.model_dump()
        dialog = getattr(ptdialogs, args.pop('type'))
        return dialog(**args)

    return [
        await env.show_dialog(dialog)
        for dialog in map(model, questions)
    ]
