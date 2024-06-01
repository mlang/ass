from base64 import b64encode

from pydantic import HttpUrl

from ass.tools import Function

class firefox(Function, help="Allow access to Firefox."):
    """Describe a screenshot from a page opened in Firefox."""

    url: HttpUrl
    full_page: bool = False
    instructions: str = "Please describe the screenshot."
    temperature: float = 0.5

    async def __call__(self, env):
        async with env.client.playwright as playwright:
            async with await playwright.firefox.launch(headless=True) as browser:
                page = await browser.new_page()
                await page.goto(str(self.url))
                await page.wait_for_load_state("load")
                png = await page.screenshot(full_page=self.full_page)
                response = await env.client.openai.chat.completions.create(
                    model='gpt-4o', temperature=self.temperature,
                    messages=[
                        {'role': 'system', 'content': self.instructions},
                        {'role': 'user', 'content': [image_url(png)]}
                    ]
                )
                return response.choices[0].message.content


def image_url(png):
    return {
        'type': 'image_url',
        'image_url': {
            'url': f"data:image/png;base64,{b64encode(png).decode()}",
            'detail': 'high'
        }
    }
