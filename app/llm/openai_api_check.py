import asyncio
import os
from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv()

client = AsyncOpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)


async def main():
    try:
        response = await client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {"role": "user", "content": "Say hello"}
            ],
            max_tokens=10
        )

        print("✅ OpenAI paid API is working!\n")

        print("Response:")
        print(response.choices[0].message.content)

        print("\nToken Usage:")
        print(response.usage)

    except Exception as e:
        print("❌ API request failed:")
        print(e)


asyncio.run(main())

#sync style for quick testing without async setup
# from openai import OpenAI

# client = OpenAI(api_key="YOUR_API_KEY")

# models = client.models.list()

# for model in models.data:
#     print(model.id)