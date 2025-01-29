# Standart
import logging
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
    send_redis_pubsub,
    subscribe_redis_pubsub,
    redis_client
)

# First party
from schema import ConfigurationRequest
from postgres.service import (
    create_configuration,
    get_entity_by_params, create_task
)
from exceptions import ModelValidateError
from postgres.session import async_session


@asynccontextmanager
async def lifespan(app: FastAPI):
    # TODO: При запуске также проверяется, все ли конфигурации были отправлены
    await subscribe_redis_pubsub(channel="completed_tasks")
    yield
    await redis_client.aclose()

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
    configured = False
    task_created = False

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

        configured = True

        task = await create_task(
            session=session,
            configuration_id=configuration.id
        )

        task_created = True

        await send_redis_pubsub(
            msg={
                "taskId": str(task.id),
                "device_id": id,
                "username": body.parameters[0].username,
                "password": body.parameters[0].password,
                "vlan": body.parameters[0].vlan,
                "interfaces": body.parameters[0].interfaces
            },
            channel="processing_tasks"
        )

        task.status = "sent"

        await session.commit()

        return JSONResponse(
            status_code=200,
            content={
                "code": 200,
                "taskId": str(task.id)}
        )

    except Exception as _:
        # TODO: логгирование ошибок
        if configured and task_created:
            await session.commit()
        # TODO: рассмотреть случай, если сама таска не была создана
        else:
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
        model=Configuration,
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
    else:
        return JSONResponse(
            status_code=204,
            content={
                "code": 204,
                "message": "Task is still running"})


