import asyncio
import os
import sys
import redis.asyncio as aioredis
from redis.exceptions import ResponseError
import aiohttp
import json
import logging
from dotenv import load_dotenv


load_dotenv()


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Script")


HOST = os.getenv("REDIS_HOST", "localhost")
PORT = os.getenv("REDIS_PORT", 6379)
CONNECTION_URL = f"redis://{HOST}:{PORT}/0"
CONSUMER_STREAM_NAME = "processing_tasks"
CONSUMER_GROUP_NAME = "proccessing_tasks_handler"
CONSUMER_NAME = "Script"
RECEIVER_STREAM_NAME = "completed_tasks"
SERVICE_A = os.getenv("SERVICE_A", "localhost:8000")


class ServiceA:

    BASE_URL = f'http://{HOST}/api/v1/equipment/cpe/'
    headers = {'Content-Type': 'application/json'}

    async def configure_equipment_by_task_from_broker(self, task: dict):

        data = {
            "timeoutInSeconds": task["timeout_in_seconds"],
            "parameters": [
                {
                    "username": task["username"],
                    "password": task["password"],
                    "vlan": task["vlan"],
                    "interfaces": task["interfaces"]
                }
            ]
        }

        async with aiohttp.ClientSession() as client:
            try:
                async with client.post(
                    url=self.BASE_URL + task.pop("device_id"),
                    headers=self.headers,
                    data=json.dumps(data)
                ) as response:
                    return await response.json()
            except aiohttp.ClientError as e:
                logger.error(f"Сервис A не доступен: {e}")
                return None


class TaskManager:

    def __init__(self):
        try:
            self.redis = aioredis.from_url(
                url=CONNECTION_URL,
                encoding="utf-8",
                decode_responses=True
            )
        except Exception as e:
            logger.error(f"Не удалось подключиться к Redis: {str(e)}")
            sys.exit(1)

    async def connect_to_consumers_group(self):
        try:
            await self.redis.xgroup_create(CONSUMER_STREAM_NAME, CONSUMER_GROUP_NAME, mkstream=True)
        except ResponseError as error:
            if "BUSYGROUP" in str(error):
                logger.info(f"Группа {CONSUMER_GROUP_NAME} уже существует")
            else:
                logger.error(f"Ошибка при создании группы : {error}")

    async def check_tasks_from_service_b(self, stream_viewing_type: str = '0'):
        messages = await self.redis.xreadgroup(
            groupname=CONSUMER_GROUP_NAME,
            consumername=CONSUMER_NAME,
            streams={CONSUMER_STREAM_NAME: stream_viewing_type},
            block=5000
        )

        tasks = {}

        if bool(messages):
            for msg_id, msg_body in messages[0][1]:

                try:
                    task = json.loads(msg_body["message"])
                except KeyError:
                    logger.error(f"Отсутствует поле message в сообщении {msg_body}")
                    return

                tasks[msg_id] = task
                logger.info(f"Получено задание {task["taskId"]} из канала {CONSUMER_STREAM_NAME}")

        return tasks

    async def send_data_to_service_a(self, task: dict):
        result = await ServiceA().configure_equipment_by_task_from_broker(
            task=task
        )

        return result

    async def send_completed_task_to_broker(self, task_id):
        await self.redis.xadd(RECEIVER_STREAM_NAME, {"taskId": task_id})

    async def confirm_receipt(self, message_id):
        await self.redis.xack(CONSUMER_STREAM_NAME, "processing_group", message_id)

    async def work(self):
        await self.connect_to_consumers_group()
        old_tasks = await self.check_tasks_from_service_b()

        if old_tasks:
            logger.info(f"Получено {len(old_tasks)} старых заданий из канала {CONSUMER_STREAM_NAME}")
            for message_id, task in old_tasks.items():
                logger.info(f"Отправка задания {task['taskId']} в сервис А")
                result = await self.send_data_to_service_a(
                    task=task
                )

                if result["message"] == "success":
                    await self.send_completed_task_to_broker(task["taskId"])
                await self.confirm_receipt(message_id=message_id)
                logger.info(f"Задание {task['taskId']} обработано")
        else:
            logger.info(f"Нет старых заданий в канале {CONSUMER_STREAM_NAME}")

        while True:
            new_tasks = await self.check_tasks_from_service_b(stream_viewing_type='>')
            if new_tasks:
                logger.info(f"Получено {len(old_tasks)} заданий из канала {CONSUMER_STREAM_NAME}")
                for message_id, task in new_tasks.items():
                    logger.info(f"Отправка задания {task['taskId']} в сервис А")
                    result = await self.send_data_to_service_a(
                        task=task
                    )

                    if result["message"] == "success":
                        await self.send_completed_task_to_broker(task["taskId"])
                    await self.confirm_receipt(message_id=message_id)
                    logger.info(f"Задание {task['taskId']} обработано")
            else:
                logger.info(f"Нет новых заданий в канале {CONSUMER_STREAM_NAME}")


async def main():

    task_manager = TaskManager()
    try:
        await task_manager.work()
    except Exception as e:
        await task_manager.redis.aclose()
        logging.critical(f"Произошла ошибка: {e}")


if __name__ == "__main__":
    asyncio.run(main())
