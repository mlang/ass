from typing import List, Literal

from pydantic import BaseModel, Field

from ass.ptutils import ConfirmDialog, MultipleChoiceDialog, TextInputDialog
from ass.tools import function

class Confirm(BaseModel):
    """A message dialog which asks the user to either confirm or deny.  Return type is a boolean value.  Use this for "Yes/No" questions."""
    type: Literal['ConfirmDialog']
    title: str = Field(description="The title of the dialog box.")
    text: str = Field(
        description="The message text to display in the dialog box."
    )
    yes_label: str = Field("Yes",
        description="The label of the confirmation button."
    )
    no_label: str = Field("No",
        description="The label of the button which cancels the dialog."
    )

class TextInput(BaseModel):
    """A dialog which allows the user to enter a string.  Return type is either a string or null, which indicates the user cancelled the dialog."""
    type: Literal['TextInputDialog']
    title: str
    text: str
    ok_label: str = "OK"
    cancel_label: str = "Cancel"

class MultipleChoice(BaseModel):
    """A multiselect list dialog.  Use this when querying the user for several selections.  Return type is a list of all selected items."""
    type: Literal['MultipleChoiceDialog']
    title: str = Field(description="The title of the dialog box.")
    text: str = Field(description="Text displayed above of the checkbox list.")
    values: List[str] = Field(
        min_length=2,
        max_length=32,
        description="The checkbox items."
    )
    ok_label: str = "OK"
    cancel_label: str = "Cancel"


@function(
    "Execute a sequence of dialogs.  Choose amongst the available dialog box types approriately.",
    "Allow prompting."
)
class dialogs(BaseModel):
    questions: List[Confirm | TextInput | MultipleChoice] = Field(
        description="List of dialogs to pop up in sequence.",
        min_length=1, max_length=99
    )

    async def __call__(self, show_dialog, client):
        results = []
        for question in self.questions:
            args = question.model_dump()
            dialog = globals()[args.pop('type')]
            results.append(await show_dialog(dialog(**args)))
        return results
