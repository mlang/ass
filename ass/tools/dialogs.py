from typing import List, Literal

from pydantic import BaseModel, Field

import ass.ptutils as ptdialogs
from ass.tools import function

class ConfirmDialog(BaseModel):
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

class TextInputDialog(BaseModel):
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


class PathInputDialog(BaseModel):
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


class RadioListDialog(BaseModel):
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


class CheckboxListDialog(BaseModel):
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


@function("Allow the model to pop up dialog boxes.")
class dialogs(BaseModel):
    """Execute a sequence of modal dialogs.
    Use this to inquire information from the user.
    Always use it when asked to generate a quiz.
    Make sure to customize the button labels according to the conversation language.
    """

    questions: List[ ConfirmDialog
                   | RadioListDialog
                   | CheckboxListDialog
                   | TextInputDialog
                   | PathInputDialog
                   ] = Field(
        description="List of modal dialogs to pop up in sequence.  Returns a list of the results. Make sure to set the discriminator 'type' of each dialog correctly.",
        min_length=1, max_length=99,
        discriminator='type'
    )

    model_config = dict(
        json_schema_extra=dict(
            examples=[
                dict(
                    questions=[
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
        )
    )

    async def __call__(self, show_dialog, client):
        def model(question):
            args = question.model_dump()
            dialog = getattr(ptdialogs, args.pop('type'))
            return dialog(**args)

        return list(
            await show_dialog(dialog) for dialog in map(model, self.questions)
        )
