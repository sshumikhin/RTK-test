import json
from uuid import UUID

import redis.asyncio as aioredis
import asyncio
from fastapi_utilities import repeat_every
from dotenv import load_dotenv
from redis.exceptions import ResponseError
from postgres.models import Task
from postgres.service import get_entity_by_params
from postgres.session import async_session
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
    try:
        await redis_client.xgroup_create(stream_name, group_name, mkstream=True)
    except ResponseError as _:
        pass

    messages = await redis_client.xreadgroup(
            group_name,
            consumer_name,
            {stream_name: '>'},
            count=1,
            block=5000
    )

    if messages:
        for item in messages:
            stream = item[0]
            messages_list = item[1]
            for message_id, message_data in messages_list:
                print(message_data)
                completed_task_id = message_data["taskId"]
                async with async_session.async_session() as session:
                    task = await get_entity_by_params(
                        model=Task,
                        session=session,
                        conditions=[Task.id == UUID(completed_task_id)]
                    )
                    task.status = "completed"
                    await session.commit()

                # Обновляем статус заявки
                # Говорим брокеру, что сообщение получено