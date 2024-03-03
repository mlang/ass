from typing import List
from pydantic import BaseModel, Field

from ass.ptutils import ConfirmDialog, TextInputDialog
from ass.tools import function

class Confirm(BaseModel):
    title: str
    text: str
    yes: str = "Yes"
    no: str = "No"

class TextInput(BaseModel):
    title: str
    text: str
    ok: str = "OK"
    cancel: str = "Cancel"


@function(
    "Ask the user a series of questions.",
    "Allow prompting."
)
class dialogs(BaseModel):
    questions: List[Confirm | TextInput] = Field(
        description="List of dialogs to pop up in sequence.",
        min_length=1
    )

    async def __call__(self, show_dialog, client):
        dialog = {
            Confirm: ConfirmDialog,
            TextInput: TextInputDialog
        }
        results = []
        for question in self.questions:
            results.append(
                await show_dialog(
                    dialog[type(question)](**question.model_dump())
                )
            )
        return results
