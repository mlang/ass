from email.mime.text import MIMEText
from typing import Annotated, List

from aiosmtplib import SMTP

from pydantic import NameEmail, Field

from ass.tools import Function

class sendmail(Function, help="Allow the model to send e-Mail via SMTP."):
    """Send an e-Mail."""
    sender: str = 'mlang+assistant@blind.guru'
    to: List[NameEmail] = Field(min_length=1)
    subject: Annotated[str, Field(strip_whitespace=True, min_length=1)]
    body: Annotated[str, Field(min_length=1)]

    validate_certs: bool = False


    def mail(self):
        mail = MIMEText(self.body, "plain", "utf-8")
        mail['To'] = ", ".join(map(str, self.to))
        mail['Subject'] = self.subject

        return mail


    async def __call__(self, env):
        async with SMTP(validate_certs=self.validate_certs) as smtp:
            return await smtp.sendmail(
                self.sender, list(map(str, self.to)), bytes(self.mail())
            )
