"""ORF News scraper."""

import re
from asyncio import gather, run

from bs4 import BeautifulSoup
import httpx
from markdownify import markdownify # type: ignore

from ass.tools import tool, Function


@tool("Enable fetching news from ORF.")
class orf_news(Function):
    """Fetch current local news from ORF."""

    async def __call__(self, env):
        return await news(env.client.http)


__all__ = ['news']

def decompose_all(element, patterns):
    for name, attrs in patterns:
        kwargs = {}
        if attrs is not None:
            kwargs['attrs'] = attrs
        while e := element.find(name, **kwargs):
            e.decompose()

async def news(http):
    response = await http.get('https://news.orf.at/')
    soup = BeautifulSoup(response.text, features="html.parser")

    async def story(article):
        headline = article.h3.get_text().strip()
        url = article.h3.a['href'].strip()
        story = article.find('div', attrs={'class': 'story-story'})
        if story is None:
            response = await http.get(url)
            soup = BeautifulSoup(response.text, features='html.parser')
            story = soup.find('div', attrs={'class': 'story-story'})
        if story is not None:
            decompose_all(story, [
                ('figure', None),
                ('footer', {'class': 'credits'}),
                ('img', None),
                ('section', {'class': 'stripe'})
            ])
            story = markdownify(story.decode_contents().strip()).strip()
        return {
            'headline': headline,
            'url': url,
            **({'story': story} if story is not None else {})
        }

    return await gather(*(map(story, soup.find_all('article'))))


async def weather(station):
    async with httpx.AsyncClient() as http:
        response = await http.get(f'https://wetter.orf.at/{station}/')
        soup = BeautifulSoup(response.text, features='html.parser')
        dataTable = soup.find('div', attrs={'class', 'dataTable'})
        def proc(tag):
            return re.sub(
                r'\s+', ' ',
                tag.get_text().strip().replace('\n', '')
            )
        return list(filter(None, map(proc, dataTable.find_all('p'))))

def graz():
    return run(weather('steiermark/grazuniversitaet'))
