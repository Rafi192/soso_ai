import asyncio
import os
from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv()

client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))


async def main():
    try:
        print(" OpenAI API is working.\n")
        print("Available models:\n")

        count = 0

        async for model in client.models.list():
            
            print("-", model.id)

            count += 1
            if count >= 20:   
                break

    except Exception as e:
        print(" Error connecting to OpenAI API:")
        print(e)


asyncio.run(main())


#sync style for quick testing without async setup
# from openai import OpenAI

# client = OpenAI(api_key="YOUR_API_KEY")

# models = client.models.list()

# for model in models.data:
#     print(model.id)