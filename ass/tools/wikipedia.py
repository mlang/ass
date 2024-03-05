from typing import Literal
from xml.etree import ElementTree

from pydantic import BaseModel

from ass.tools import function


@function("Allow access to wikipedia.")
class wikipedia(BaseModel):
    """Fetch a wikipedia article by page name."""

    lang: Literal['de', 'en', 'es', 'fr', 'it', 'nl', 'no', 'pt', 'ro'] = 'en'
    page: str

    async def __call__(self, show_dialog, client):
        response = await client.http.get(
            f"https://{self.lang}.wikipedia.org/w/index.php",
            params=dict(title='Special:Export', pages=self.page),
            follow_redirects=True
        )
        wikimedia = ElementTree.fromstring(response.text)
        ns = '{http://www.mediawiki.org/xml/export-0.10/}'
        return wikimedia.find(f'{ns}page/{ns}revision/{ns}text').text
