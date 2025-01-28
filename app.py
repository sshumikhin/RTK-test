# Standart
import asyncio
import json
import random

import aio_pika
from aio_pika import ExchangeType
# Third party
from fastapi import FastAPI, Path, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from exceptions import ModelValidateError
from postgres.session import async_session

# First party
from schema import ConfigurationRequest
from postgres.service import create_equipment_configuration, get_task_by_id

app = FastAPI(
    title="service-b",
    responses={
        500: {
            "content": {
                "application/json": {
                    "example": {
                        "code": 500,
                        "message": "Internal provisioning exception"
                    }
                }
            },
            "description": "Внутренняя ошибка"
        }
    }
)


@app.exception_handler(ModelValidateError)
async def http_exception_handler(request, exc):
    return JSONResponse(
        status_code=400,
        content={"message": str(exc)}
    )


@app.post(
    path="/api/v1/equipment/cpe/{id}",
    summary="Конфигурация устройства по ID",
    responses={
        200: {
            "content": {
                "application/json": {
                    "example": {
                        "code": 200,
                        "message": "success"
                    }
                }
            },
            "description": "Устройство успешно сконфигурировано"
        },
        404: {
            "content": {
                "application/json": {
                    "example": {
                        "code": 404,
                        "message": "The requested equipment is not found"
                    }
                }
            },
            "description": "Устройство не найдено"
        }
    }
)
async def configure_device_by_id(
    body: ConfigurationRequest,
    id: str = Path(..., title="ID устройства", regex="^[a-zA-Z0-9]{6,}$"),
    session: AsyncSession = Depends(async_session)
):
    # TODO: сохранять входные данные
    try:
        task = await create_equipment_configuration(
            session=session,
            device_id=id,
            timeout_in_seconds=body.timeoutInSeconds,
            username=body.parameters[0].username,
            password=body.parameters[0].password,
            vlan=body.parameters[0].vlan,
            interfaces=body.parameters[0].interfaces
        )

        # TODO: Создавать задачу
        connection = await aio_pika.connect_robust("amqp://guest:guest@localhost/")
        channel = await connection.channel()

        exchange = await channel.declare_exchange(
            name="tasks_exchange",
            type=aio_pika.ExchangeType.DIRECT
        )

        queue = await channel.declare_queue("tasks_queue")

        message_body = json.dumps(body.model_dump())
        message = aio_pika.Message(body=message_body.encode(), content_type='application/json')

        await exchange.publish(message, routing_key="send_task")

        await session.commit()

        return JSONResponse(status_code=200, content={"taskId": str(task.task_id)})

    except Exception as _:
        #TODO: логгирование ошибок
        await session.rollback()
        return JSONResponse(status_code=500, content={"message": "Internal provisioning exception"})


@app.get(
    path="/api/v1/equipment/cpe/{id}/task/{task}",
    summary="Получить статус задачи",
    responses={
         200: {
             "content": {
                    "application/json": {
                     "example": {
                         "code": 200,
                         "message": "Completed"
                    }
                 }
             },
            "description": "Задача завершена"
         },
         204: {
            "content": {
                "application/json": {
                         "example": {
                             "code": 204,
                             "message": "Task is still running"
                         }
                     }
                 },
                 "description": "Задача выполняется"
             },
             404: {
                 "content": {
                     "application/json": {
                         "example": {
                             "code": 404,
                             "message": "The requested task is not found"
                         },
                         "second_example": {
                                 "code": 404,
                                 "message": "The requested equipment is not found"
                         }
                     }
                 },
                 "description": "Задача или устройство не найдено"
             }
         })
async def get_task_status(
        id: str = Path(..., title="ID устройства", regex="^[a-zA-Z0-9]{6,}$"),
        task: str = Path(..., title="ID задачи"),
        session: AsyncSession = Depends(async_session)
):
    task = await get_task_by_id(
        session=session,
        task_id=task
    )

    if task is None:
        pass

#     try:
#         # Проверка наличия устройства
#         if id not in devices:
#             raise HTTPException(status_code=404, detail="The requested equipment is not found")
#
#         # Проверка наличия задачи
#         if task not in tasks_status:
#             raise HTTPException(status_code=404, detail="The requested task is not found")
#
#         # Возвращение статуса задачи
#         if tasks_status[task] == "completed":
#             return {"code": 200, "message": "Completed"}
#         else:
#             return {"code": 204, "message": "Task is still running"}
#     except Exception as e:
#         raise HTTPException(status_code=500, detail="Internal provisioning exception")



# TODO: закрывать redis при закрытии приложения