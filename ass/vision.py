from asyncio import run
from base64 import b64encode
from io import BytesIO

from click import File, argument, command, option, pass_obj
from PIL import Image


@command(help="Obtain an image description.")
@option('--instructions',
        help="Instructions for the vision model.",
        default="""Describe the image in detail.""",
        show_default=True
)
@option('--model',
        help="Which model to use for image description.",
        default='gpt-4o-2024-05-13',
        show_default=True
)
@option('-n',
        default=1,
        help="Number of initial descriptions to generate."
)
@option('--summary-instructions',
        help="Instructions for the summarizer.",
        default="""You will be given several descriptions of the same picture from different sources.  Your task is to create a coheren and concise summary of the picture.""",
        show_default=True
)
@option('--summary-model',
        help="Model to use for summaries.",
        default='gpt-4o-2024-05-13',
        show_default=True
)
@option('--temperature',
        help="Temperature (a value between 0.0 and 2.0).",
        default=0.8,
        show_default=True
)
@argument("file", type=File('rb'))
@pass_obj
def describe_image(client, file, **kwargs):
    print(run(adescribe(client.openai, image_url(file), **kwargs)))


async def adescribe(
    openai, image_url,
    model, instructions, n, summary_model, summary_instructions, temperature
):
    response = await openai.chat.completions.create(
        model=model, max_tokens=1024, n=n, temperature=temperature,
        messages=[dict(role='system', content=instructions),
            dict(role='user', content=[image_url])
        ]
    )
    if len(response.choices) > 1:
        response = await openai.chat.completions.create(
            model=summary_model, max_tokens=1024, temperature=temperature,
            messages=[dict(role='system', content=summary_instructions),
                *(dict(role='user', content=choice.message.content)
                  for choice in response.choices
                 )
            ]
        )

    return response.choices[0].message.content


def image_url(file):
    return dict(type="image_url",
        image_url=dict(url=data_url(clip(Image.open(file), 2000, 768)),
            detail="high"
        )
    )


def clip(image, long, short):
    w, h = image.size

    def shrink(f, n):
        nonlocal w, h
        x = f(w, h)
        if x > n:
            factor = n / x
            h = h * factor
            w = w * factor

    shrink(max, long)
    shrink(min, short)

    return (
        image.resize((round(w), round(h))) if (w, h) != image.size else image
    )


def data_url(image):
    buffer = BytesIO()
    image.save(buffer, format="JPEG")

    return f"data:image/jpeg;base64,{b64encode(buffer.getvalue()).decode()}"
