import json
import redis.asyncio as aioredis
import asyncio
from fastapi_utilities import repeat_every
from dotenv import load_dotenv

from postgres.models import Task
from postgres.service import get_entity_by_params
from utils import getenv


load_dotenv()

HOST = getenv("REDIS_HOST")
PORT = getenv("REDIS_PORT")

CONNECTION_URL = F"redis://{HOST}:{PORT}/0"

redis_client = aioredis.from_url(
                url=CONNECTION_URL,
                encoding="utf-8",
                decode_responses=True
            )


async def send_redis_pubsub(msg: dict, channel: str):
    message_body = json.dumps(msg)
    await redis_client.publish(channel, message_body)


@repeat_every(seconds=5)
async def subscribe_redis_pubsub(channel: str):
    pubsub = redis_client.pubsub()
    await pubsub.subscribe(channel)

    while True:
        message = await pubsub.get_message()
        if message and message.get("taskId", False):
            print(message)
        await asyncio.sleep(0.1)