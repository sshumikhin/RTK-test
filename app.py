# Standart
from uuid import UUID
from contextlib import asynccontextmanager

# Third party
from fastapi import (FastAPI,
                     Path,
                     Depends,
                     Request
)
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from postgres.models import (
    Task,
    Configuration
)

from redis_client import (
    read_from_stream,
    redis_client,
    send_to_stream, create_consumer_group, read_old_messages
)

# First party
from schema import ConfigurationRequest
from postgres.service import (
    create_configuration,
    get_entity_by_params, create_task
)
from exceptions import ModelValidateError
from postgres.session import async_session
import logging


logger = logging.getLogger("Service B")
logger.setLevel(logging.INFO)


CONSUMER_STREAM_NAME = "completed_tasks"
CONSUMER_GROUP_NAME = "completed_tasks_handler"
CONSUMER_NAME = "Service B"


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Запуск сервиса B")

    await create_consumer_group(
        stream=CONSUMER_STREAM_NAME,
        group=CONSUMER_GROUP_NAME,
    )

    await read_old_messages(
        group=CONSUMER_GROUP_NAME,
        consumername=CONSUMER_NAME,
        stream=CONSUMER_STREAM_NAME
    )
    await read_from_stream(
        groupname=CONSUMER_GROUP_NAME,
        consumername=CONSUMER_NAME,
        stream=CONSUMER_STREAM_NAME
    )
    yield
    await redis_client.aclose()
    logger.info("Остановка сервиса B")


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
    },
    lifespan=lifespan
)


@app.exception_handler(ModelValidateError)
async def http_exception_handler(_: Request, exc):
    return JSONResponse(
        status_code=400,
        content={
            "code": 400,
            "message": str(exc)}
    )


@app.exception_handler(Exception)
async def http_exception_handler(_: Request, exc):
    return JSONResponse(
        status_code=500,
        content={
            "code": 500,
            "message": "Internal provisioning exception"}
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
    try:
        configuration = await create_configuration(
            session=session,
            device_id=id,
            timeout_in_seconds=body.timeoutInSeconds,
            username=body.parameters[0].username,
            password=body.parameters[0].password,
            vlan=body.parameters[0].vlan,
            interfaces=body.parameters[0].interfaces
        )


        task = await create_task(
            session=session,
            configuration_id=configuration.id
        )

        await send_to_stream(
            msg={
                "taskId": str(task.id),
                "device_id": id,
                "username": body.parameters[0].username,
                "password": body.parameters[0].password,
                "vlan": body.parameters[0].vlan,
                "interfaces": body.parameters[0].interfaces,
                "timeout_in_seconds": body.timeoutInSeconds
            },
            stream_name="processing_tasks"
        )

        task.status = "sent"

        await session.commit()

        logger.info(f"Задача {task.id} отправлена в Redis stream")

        return JSONResponse(
            status_code=200,
            content={
                "code": 200,
                "taskId": str(task.id)}
        )

    except Exception as e:
        logger.critical(msg=str(e), exc_info=True)
        await session.rollback()
        return JSONResponse(
            status_code=500,
            content={
                "code": 500,
                "message": "Internal provisioning exception"})


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
        task: UUID,
        id: str = Path(
            default = ...,
            title="ID устройства",
            regex="^[a-zA-Z0-9]{6,}$"
        ),
        session: AsyncSession = Depends(async_session)
):

    configuration_ids = await get_entity_by_params(
        model=Configuration.id,
        session=session,
        conditions=[Configuration.device_id == id],
        many=True
    )

    if not bool(configuration_ids):
        return JSONResponse(
            status_code=404,
            content={
                "code": 404,
                "message": "The requested equipment is not found"}
        )

    task = await get_entity_by_params(
        model=Task,
        session=session,
        conditions=[Task.configuration_id.in_(configuration_ids),
                    Task.id == task],
    )

    if task is None:
        return JSONResponse(
            status_code=404,
            content={
                "code": 404,
                "message": "The requested task is not found"}
    )

    if task.status == "completed":
        return JSONResponse(
            status_code=200,
            content={
                "code": 200,
                "message": "Completed"}
        )
    elif task.status == "sent":
        return JSONResponse(
            status_code=204,
            content={
                "code": 204,
                "message": "Task is still running"})
    else:
        logger.critical(msg=f"Unknown task status. task_id ={task.id}")
        return JSONResponse(
            status_code=204,
            content={
                "code": 204,
                "message": "Task is still running"})
