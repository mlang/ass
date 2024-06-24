from typing import Literal
from xml.etree import ElementTree

from ass.oai import function


Lang = Literal['de', 'en', 'es', 'fr', 'it', 'nl', 'no', 'pt', 'ro']

export = '{http://www.mediawiki.org/xml/export-0.11/}'

@function(help="""Allow access to wikipedia.""")
async def wikipedia(env, /, *, lang: Lang = 'en', page: str):
    """Fetch a wikipedia article (in Wikimedia format) by page name."""

    response = await env.client.http.get(
        f"https://{lang}.wikipedia.org/w/index.php",
        params={'title': 'Special:Export', 'pages': page},
        follow_redirects=True
    )
    response.raise_for_status()
    wikimedia = ElementTree.fromstring(response.text)
    p = wikimedia.find(f'{export}page')
    if p is None:
        return {'error': """There is no page with that name."""}
    latest = p.find(f'{export}revision/{export}text')
    if latest is None:
        return {'error': """Could not extract text of latest revision from XML"""}
    return latest.text
