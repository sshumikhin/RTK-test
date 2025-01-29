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

CONNECTION_URL = f"redis://{HOST}:{PORT}/0"

redis_client = aioredis.from_url(
    url=CONNECTION_URL,
    encoding="utf-8",
    decode_responses=True
)


async def send_to_stream(msg: dict, stream_name: str):
    message_body = json.dumps(msg)
    await redis_client.xadd(stream_name, {"message": message_body})


@repeat_every(seconds=5)
async def read_from_stream(stream_name: str, group_name: str, consumer_name: str):
    await redis_client.xgroup_create(stream_name, group_name, mkstream=True)

    while True:
        messages = await redis_client.xreadgroup(group_name, consumer_name, {stream_name: '>'}, count=1, block=5000)

        if messages:
            for stream, messages_list in messages.items():
                for message_id, message_data in messages_list:
                    message_body = message_data["message"]
                    print(f"Получено сообщение: {message_body}")

                    await redis_client.xack(stream_name, group_name, message_id)

