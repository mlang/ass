from abc import abstractmethod
from base64 import b64encode
from typing import Literal, Union

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from ass.tools import Function


class PageAction(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)

    @abstractmethod
    async def __call__(self, page):
        ...


class goto(PageAction):
    """Go to the given URL."""
    url: HttpUrl

    async def __call__(self, page):
        await page.goto(str(self.url))


class locator(PageAction):
    """Select a page element and perform an action on it."""

    selector: str = Field(description="A playwright selector.")
    method: Literal['click', 'check', 'uncheck']

    async def __call__(self, page):
        await getattr(page.locator(self.selector), self.method)()


class screenshot(PageAction):
    full_page: bool = False

    async def __call__(self, page):
        return await page.screenshot(type='png', full_page=self.full_page)


class browser(Function, help="Allow access to a graphical browser."):
    """Interact with a browser.
    After the action was performed, a screenshot is taken which will be
    described by a vision capable model.
    """

    browser: Literal['chromium', 'firefox', 'webkit'] = "firefox"
    action: Union[goto | locator]

    screenshot: screenshot

    model: Literal['gpt-4o'] = "gpt-4o"
    instructions: str = """You are a screen reader.  Describe the screenshot accordingly.  Guess the role of each page element such that playwright selectors can be written for them."""
    max_tokens: int = Field(2048, ge=100, le=4096)
    temperature: float = Field(0.5, ge=0.0, le=1.5)
    n: int = Field(1, ge=1, le=5)

    async def __call__(self, env):
        page = await get_page(env.client.playwright, self.browser)
        await self.action(page)
        png = await self.screenshot(page)
        return await self.describe(env.client.openai.chat.completions, png)

    async def describe(self, completions, png):
        response = await completions.create(
            model=self.model,
            max_tokens=self.max_tokens, n=self.n, temperature=self.temperature,
            messages=[
                {'role': 'system', 'content': self.instructions},
                {'role': 'user', 'content': [image_url(png)]}
            ]
        )
        return [choice.message.content for choice in response.choices]


_browser = {}
_context = {}
_page = {}

async def get_page(playwright, browser: str):
    global _browser, _context, _page
    if browser not in _page:
        if browser not in _context:
            if browser not in _browser:
                _browser[browser] = await getattr(playwright, browser).launch(headless=True)
            _context[browser] = await _browser[browser].new_context()
        _page[browser] = await _context[browser].new_page()
    return _page[browser]


def image_url(png):
    return {
        'type': 'image_url',
        'image_url': {
            'url': f"data:image/png;base64,{b64encode(png).decode()}",
            'detail': 'high'
        }
    }
