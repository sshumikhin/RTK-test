import json
from uuid import UUID
import redis.asyncio as aioredis
from fastapi_utilities import repeat_every
from dotenv import load_dotenv
from redis.exceptions import ResponseError
from postgres.models import Task
from postgres.service import get_entity_by_params
from postgres.session import async_session
from utils import getenv
import logging

load_dotenv()

HOST = getenv("REDIS_HOST")
PORT = getenv("REDIS_PORT")

CONNECTION_URL = f"redis://{HOST}:{PORT}/0"

logger = logging.getLogger("uvicorn.info")


redis_client = aioredis.from_url(
    url=CONNECTION_URL,
    encoding="utf-8",
    decode_responses=True
)


async def send_to_stream(msg: dict, stream_name: str):
    message_body = json.dumps(msg)
    await redis_client.xadd(stream_name, {"message": message_body})


async def create_consumer_group(stream: str, group: str):
    logger.info(f"Создание группы {group} для потока {stream}")
    try:
        await redis_client.xgroup_create(stream, group, mkstream=True)
    except ResponseError as error:
        if "BUSYGROUP" in str(error):
            logger.info(f"Группа {group} уже существует")
        else:
            logger.error(f"Ошибка при создании группы : {error}")


async def read_old_messages(stream: str, group: str, consumername: str):

    messages = await redis_client.xreadgroup(
            groupname=group,
            consumername=consumername,
            streams={stream: '0'},
            block=5000
    )
    if bool(messages):
        for msg_id, msg_body in messages[0][1]:
            try:
                task_id = json.loads(msg_body)["taskId"]
            except KeyError:
                logger.error(f"Отсутствует поле taskId в сообщении {msg_body}")
                return
            async with async_session.async_session() as session:
                task = await get_entity_by_params(
                    model=Task,
                    session=session,
                    conditions=[Task.id == UUID(task_id)]
                )
                task.status = "completed"
                await session.commit()
                logger.info(f"Задача {task.id} успешно выполнена")
            await redis_client.xack(stream, group, msg_id)


@repeat_every(seconds=5)
async def read_from_stream(groupname: str, consumername: str, stream: str):
    messages = await redis_client.xreadgroup(
            groupname=groupname,
            consumername=consumername,
            streams={stream: '>'},
            block=5000
    )
    if bool(messages):
        for msg_id, msg_body in messages[0][1]:
            try:
                task_id = json.loads(msg_body)["taskId"]
            except KeyError:
                logger.error(f"Отсутствует поле taskId в сообщении {msg_body}")
                return
            async with async_session.async_session() as session:
                task = await get_entity_by_params(
                    model=Task,
                    session=session,
                    conditions=[Task.id == UUID(task_id)]
                )
                task.status = "completed"
                await session.commit()
                logger.info(f"Задача {task.id} успешно выполнена")
            await redis_client.xack(stream, groupname, msg_id)
