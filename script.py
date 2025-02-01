"""
    Скрипт, взаимодействующий с брокером сообщений и сервисом А
"""

# Standart
import os
import sys
import json
import logging

# Third party
import asyncio
import redis.asyncio as aioredis
from redis.exceptions import ResponseError
import aiohttp
from dotenv import load_dotenv


load_dotenv()

logger = logging.getLogger("Script")
logger.setLevel(logging.INFO)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

file_handler = logging.FileHandler('errors.log')
file_handler.setLevel(logging.ERROR)

formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

console_handler.setFormatter(formatter)
file_handler.setFormatter(formatter)

logger.addHandler(console_handler)
logger.addHandler(file_handler)

HOST = os.getenv("REDIS_HOST", "localhost")
PORT = os.getenv("REDIS_PORT", 6379)
CONNECTION_URL = f"redis://{HOST}:{PORT}/0"
CONSUMER_STREAM_NAME = "processing_tasks"
CONSUMER_GROUP_NAME = "proccessing_tasks_handler"
CONSUMER_NAME = "Script"
RECEIVER_STREAM_NAME = "completed_tasks"
SERVICE_A = os.getenv("SERVICE_A", "localhost:8000")


class ServiceA:
    """
        Класс для работы с сервисом А
    """

    BASE_URL = f'http://{SERVICE_A}/api/v1/equipment/cpe/'
    headers = {'Content-Type': 'application/json'}

    async def configure_equipment_by_task_from_broker(self, task: dict):
        """
            Метод для конфигурации оборудования

            Имплементирует POST /api/v1/equipment/cpe/
        """
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
                sys.exit(1)


class TaskManager:
    """
        Класс, реализующий все функции скрипта
    """

    def __init__(self):
        """
            Метод-инициализатор, создающий соединение с Redis
        """
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
        """
            Метод, создающий группу и подключающийся в Redis Stream к потоку

            В случае если группа уже существует, то она не создается

            Имплементирует XGROUP CREATE
        """
        try:
            await self.redis.xgroup_create(CONSUMER_STREAM_NAME, CONSUMER_GROUP_NAME, mkstream=True)
        except ResponseError as error:
            if "BUSYGROUP" in str(error):
                logger.info(f"Группа {CONSUMER_GROUP_NAME} уже существует")
            else:
                logger.error(f"Ошибка при создании группы : {error}")
                sys.exit(1)

    async def check_tasks_from_service_b(self, stream_viewing_type: str = '0'):
        """
            Метод, получающий задания из сервиса B

            Имплементирует XREADGROUP
        """
        try:
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
                        sys.exit(1)

                    tasks[msg_id] = task
                    logger.info(f"Получено задание {task["taskId"]} из потока {CONSUMER_STREAM_NAME}")
            return tasks
        except Exception as e:
            logger.error("Не удалось получить сообщения из сервиса B")

    async def send_data_to_service_a(self, task: dict):
        """
            Метод для отправки задания в сервис А
        """
        result = await ServiceA().configure_equipment_by_task_from_broker(
            task=task
        )

        return result

    async def send_completed_task_to_broker(self, task_id, status: str):
        """
            Метод для отправки задания в канал для получателя(Сервис B)

            Имплементирует XADD
        """
        try:
            await self.redis.xadd(RECEIVER_STREAM_NAME, {"taskId": task_id, "status": status})
        except Exception as e:
            logger.error(f"Не удалось отправить задание в канал {RECEIVER_STREAM_NAME}: {e}")
            logger.error(f"task_id: {task_id}")
            sys.exit(1)

    async def confirm_receipt(self, message_id):
        """
            Метод для подтверждения получения и обработки задания

            Имплементирует XACK
        """
        try:
            await self.redis.xack(CONSUMER_STREAM_NAME, "processing_group", message_id)
        except Exception as e:
            logger.error(f"Не удалось подтвердить получение задания: {e}")
            logger.error(f"message_id: {message_id}")
            sys.exit(1)

    async def work(self):
        """
            Метод, реализующий цикл обработки заданий

            В данном методе применяются все вышеперечисленные методы.

            Метод описывает работу скрипта
        """
        await self.connect_to_consumers_group()

        first_run = True

        while True:
            if first_run:
                new_tasks = await self.check_tasks_from_service_b()
                first_run = False
            else:
                new_tasks = await self.check_tasks_from_service_b(stream_viewing_type='>')

            if new_tasks:
                logger.info(f"Получено {len(new_tasks)} заданий из канала {CONSUMER_STREAM_NAME}")
                for message_id, task in new_tasks.items():
                    logger.info(f"Отправка задания {task['taskId']} в сервис А")
                    result = await self.send_data_to_service_a(
                            task=task
                    )
                    if result["code"] == 200:
                        await self.confirm_receipt(message_id=message_id)
                        await self.send_completed_task_to_broker(task["taskId"], status="completed")
                        logger.info(f"Задание {task['taskId']} обработано сервисом А")

                    elif result["code"] == 404:
                        await self.send_completed_task_to_broker(task["taskId"], status="not_found")
                        await self.confirm_receipt(message_id=message_id)
                        logger.info(f"Задание {task['taskId']} не было найдено сервисом А")

                    else:
                        logger.error("Сервис A не доступен")
                        logger.error(f"task_id: {task['taskId']}")
                        # Не подтвердили обработку задачи, а значит, она остаётся в брокере
                        continue
            else:
                logger.info(f"Нет новых заданий в канале {CONSUMER_STREAM_NAME}")


async def main():
    """
        Запуск скрипта
    """

    task_manager = TaskManager()
    try:
        logger.info("Запуск скрипта")
        await task_manager.work()
    except Exception as e:
        await task_manager.redis.aclose()
        logging.critical(f"Произошла ошибка: {e}")
    finally:
        await task_manager.redis.aclose()
        logger.info("Завершение работы скрипта")


if __name__ == "__main__":
    asyncio.run(main())
