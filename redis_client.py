import json
import sys
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

logger = logging.getLogger("uvicorn")

logger.setLevel(logging.INFO)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

file_handler = logging.FileHandler('redis_errors.log')
file_handler.setLevel(logging.ERROR)

formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

console_handler.setFormatter(formatter)
file_handler.setFormatter(formatter)

logger.addHandler(console_handler)
logger.addHandler(file_handler)

try:
    redis_client = aioredis.from_url(
        url=CONNECTION_URL,
        encoding="utf-8",
        decode_responses=True
    )
except Exception as error:
    logger.error(f"Не удалось подключиться к Redis : {error}")


async def send_to_stream(msg: dict, stream_name: str):
    try:
        message_body = json.dumps(msg)
        await redis_client.xadd(stream_name, {"message": message_body})
    except Exception as error:
        logger.error(error)
        logger.error(f"Не удалось отправить сообщение в {stream_name}")
        logger.error(f"message: {str(msg)}, stream_name: {stream_name}")
        sys.exit(1)


async def create_consumer_group(stream: str, group: str):
    logger.info(f"Создание группы {group} для потока {stream}")
    try:
        await redis_client.xgroup_create(stream, group, mkstream=True)
    except ResponseError as error:
        if "BUSYGROUP" in str(error):
            logger.info(f"Группа {group} уже существует")
        else:
            logger.error(f"Ошибка при создании группы : {error}")
            sys.exit(1)


async def read_messages(
        stream: str,
        group: str,
        consumername: str,
        stream_viewing_type: str,
        periodic_message: str | None = None
):
    if periodic_message is not None:
        logger.info(periodic_message)
    try:
        messages = await redis_client.xreadgroup(
                groupname=group,
                consumername=consumername,
                streams={stream: stream_viewing_type},
                block=5000
        )
        if bool(messages):
            for msg_id, msg_body in messages[0][1]:
                try:
                    task_id = msg_body["taskId"]
                except KeyError:
                    logger.error(f"Отсутствует поле taskId в сообщении {str(msg_body)}")
                    return

                async with async_session.async_session() as session:
                    task = await get_entity_by_params(
                        model=Task,
                        session=session,
                        conditions=[Task.id == UUID(task_id)]
                    )
                    task.status = msg_body["status"]
                    await session.commit()
                    logger.info(f"Задача {task.id} успешно выполнена")
                await redis_client.xack(stream, group, msg_id)
    except Exception as error:
        logger.error(f"Не удалось прочитать сообщения")
        logger.error(error)


read_new_messages = repeat_every(seconds=5)(read_messages)
