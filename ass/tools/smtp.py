from email.mime.text import MIMEText
from typing import Annotated, List

from aiosmtplib import SMTP

from pydantic import NameEmail, Field

from ass.oai import function

@function(help="Allow the model to send e-Mail via SMTP.")
async def sendmail(env, /, *,
    sender: str = 'mlang+assistant@blind.guru',
    to: Annotated[List[NameEmail], Field(min_length=1)],
    subject: Annotated[str, Field(strip_whitespace=True, min_length=1)],
    body: Annotated[str, Field(min_length=1)],
    validate_certs: bool = False
):
    """Send an e-Mail."""

    mail = MIMEText(body, "plain", "utf-8")
    mail['To'] = ", ".join(map(str, to))
    mail['Subject'] = subject

    async with SMTP(validate_certs=validate_certs) as smtp:
        return await smtp.sendmail(sender, list(map(str, to)), bytes(mail))
