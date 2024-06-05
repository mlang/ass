from abc import abstractmethod
from base64 import b64encode
from typing import List, Literal, Optional, Union
from typing_extensions import Annotated

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from ass.tools import Function


class PageAction(BaseModel):
    model_config = ConfigDict(frozen=True)

    @abstractmethod
    async def __call__(self, page):
        ...


class goto(PageAction):
    """Go to the given URL."""
    type: Literal['goto']
    url: HttpUrl

    async def __call__(self, page):
        await getattr(page, self.type)(str(self.url))


class go_back(PageAction):
    """Go back."""
    type: Literal['go_back']

    async def __call__(self, page):
        await getattr(page, self.type)()


class accessibility(PageAction):
    """Returns a snapshot of the Accessibility Tree."""
    type: Literal['accessibility']

    async def __call__(self, page):
        return await getattr(page, self.type).snapshot()

def get_selectors(node: dict, selectors=[]):
    if 'role' in node and 'name' in node:
        role = node['role']
        name = node['name']
        if name and name not in ('heading', 'text leaf'):
            selectors.append(f'role={role}[name="{name}"]')
    if 'children' in node:
        for child in node['children']:
            get_selectors(child, selectors)

    return selectors

class list_selectors(PageAction):
    """Return a list of possible selectors for interaction with page elements."""
    type: Literal['list_selectors']

    async def __call__(self, page):
        return get_selectors(await page.accessibility.snapshot())

Selector = Annotated[str,
    Field(
        description="A playwright selector.",
        examples=[
            '''role=button[name="Submit"]''',
            '''role=link[name="more information"]'''
        ]
    )
]


class count(PageAction):
    """Count the number of page elements matched by a selector.
    Useful for validating a selector before using it to invoke an element.
    """
    type: Literal['count']
    selector: Selector

    async def __call__(self, page):
        return await getattr(page.locator(self.selector), self.type)()


class click(PageAction):
    """Locate a page element and click on it."""

    type: Literal['click']
    selector: Selector

    async def __call__(self, page):
        await getattr(page.locator(self.selector), self.type)()


class hover(PageAction):
    """Locate a page element and hover over it."""

    type: Literal['hover']
    selector: Selector

    async def __call__(self, page):
        await getattr(page.locator(self.selector), self.type)()


class check(PageAction):
    """Locate a checkbox or radio element and ensure it is checked."""

    type: Literal['check']
    selector: Selector

    async def __call__(self, page):
        await getattr(page.locator(self.selector), self.type)()


class uncheck(PageAction):
    """Locate a checkbox and ensure it is unchecked."""

    type: Literal['uncheck']
    selector: Selector

    async def __call__(self, page):
        await getattr(page.locator(self.selector), self.type)()


class fill(PageAction):
    """Locate a input field and set it."""

    type: Literal['fill']
    selector: Selector
    value: str

    async def __call__(self, page):
        await getattr(page.locator(self.selector), self.type)(self.value)


class screenshot(PageAction):
    type: Literal['screenshot']

    full_page: bool = False
    caret: Optional[Literal['hide', 'initial']] = None
    mask: Optional[List[Selector]] = None

    model: Literal['gpt-4o'] = "gpt-4o"
    instructions: str = """You are a screen reader.  Describe the screenshot accordingly."""
    max_tokens: Annotated[int, Field(ge=100, le=4096)] = 2048
    temperature: Annotated[float, Field(ge=0.0, le=1.5)] = 0.5
    n: Annotated[int, Field(ge=1, le=5)] = 1

    async def __call__(self, page):
        png = await getattr(page, self.type)(
            type='png',
            full_page=self.full_page,
            caret=self.caret,
            mask=([page.locator(selector) for selector in self.mask]
                if self.mask else None
            )
        )

        async def describe(completions):
            response = await completions.create(
                model=self.model,
                max_tokens=self.max_tokens, n=self.n, temperature=self.temperature,
                messages=[
                    {'role': 'system', 'content': self.instructions},
                    {'role': 'user', 'content': [image_url(png)]}
                ]
            )
            return [choice.message.content for choice in response.choices]

        return describe


Action = Annotated[
    Union[ goto | go_back
         | accessibility | screenshot | list_selectors
         | count | click | check | hover | uncheck | fill
         ],
    Field(discriminator='type')
]


class browser(Function, help="Allow access to a headless graphical browser."):
    """Interact with a browser.
    If the action does not return a result (like goto and go_back),
    a snapshot of the accessibility tree is returned.
    For further details, request a screenshot which is going to be
    described by a vision model according to your instructions.
    """

    browser: Literal['chromium', 'firefox', 'webkit'] = "firefox"
    action: Action

    async def __call__(self, env):
        page = await get_page(env.client.playwright, self.browser)
        if result := await self.action(page):
            if callable(result):
                result = await result(env.client.openai.chat.completions)
            return result
        return await page.accessibility.snapshot()


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
