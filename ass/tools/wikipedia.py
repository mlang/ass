from typing import Literal
from xml.etree import ElementTree

from ass.tools import function


@function(help="Allow access to wikipedia.")
async def wikipedia(env, /, *,
    lang: Literal['de', 'en', 'es', 'fr', 'it', 'nl', 'no', 'pt', 'ro'] = 'en',
    page: str
):
    """Fetch a wikipedia article by page name."""
    response = await env.client.http.get(
        f"https://{lang}.wikipedia.org/w/index.php",
        params=dict(title='Special:Export', pages=page),
        follow_redirects=True
    )
    response.raise_for_status()
    wikimedia = ElementTree.fromstring(response.text)
    ns = '{http://www.mediawiki.org/xml/export-0.10/}'
    return wikimedia.find(f'{ns}page/{ns}revision/{ns}text').text
