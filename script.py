import asyncio
import os
from typing import Dict
import redis.asyncio as aioredis
from redis.exceptions import ResponseError
import aiohttp
import json
import logging
from dotenv import load_dotenv


load_dotenv()


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Script")


class ServiceA:

    HOST = os.getenv("SERVICE_A", "localhost:8000")
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
                print(f"Ошибка при вызове сервиса A: {e}")
                return None


class TaskManager:

    PROCESSING_TASKS_STREAM_NAME = "processing_tasks"
    COMPLETED_TASKS_STREAM_NAME = "completed_tasks"

    def __init__(self):
        self.redis = aioredis.from_url(
            url = "redis://localhost",
            # encoding="utf-8",
            # decode_responses=True
        )

    async def connect_to_consumers_group(self):
        try:
            await self.redis.xgroup_create(
                name=self.PROCESSING_TASKS_STREAM_NAME,
                groupname="processing_group",
                mkstream=True
            )
        except ResponseError:
            pass

    async def check_tasks_from_service_b(self) -> Dict[str, dict]:
        messages = await self.redis.xreadgroup(
            groupname="processing_group",
            consumername="consumer",
            streams={self.PROCESSING_TASKS_STREAM_NAME: '>'},
            count=1,
            block=5000
        )
        tasks = {}
        if messages:
            for item in messages:
                stream = item[0].decode("utf-8")
                messages_list = item[1]

                for message_id, message_data in messages_list:
                    task = message_data[b"message"].decode("utf-8")
                    task_dict = json.loads(task)
                    tasks[message_id] = task_dict

        return tasks

    async def send_data_to_service_a(self, task: dict):
        result = await ServiceA().configure_equipment_by_task_from_broker(
            task=task
        )

        return result

    async def send_completed_task_to_broker(self, task_id):
        await self.redis.xadd(self.COMPLETED_TASKS_STREAM_NAME, {"taskId": task_id})

    async def confirm_receipt(self, message_id):
        await self.redis.xack(self.PROCESSING_TASKS_STREAM_NAME, "processing_group", message_id)

    async def work(self):
        await self.connect_to_consumers_group()
        while True:
            new_tasks = await self.check_tasks_from_service_b()
            if new_tasks:
                for message_id, task in new_tasks.items():
                    result = await self.send_data_to_service_a(
                        task=task
                    )

                    if result["message"] == "success":
                        await self.send_completed_task_to_broker(task["taskId"])
                    await self.confirm_receipt(message_id=message_id)

            await asyncio.sleep(1)


    # def __del__(self):
    #     asyncio.run(self.redis.aclose())
    #

if __name__ == "__main__":
    asyncio.run(TaskManager().work())
