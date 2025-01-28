# Standart
import asyncio
import random

# Third party
from fastapi import FastAPI, Path
from fastapi.responses import JSONResponse

from exceptions import ModelValidateError
# First party
from schema import ConfigurationRequest


app = FastAPI(
    title="service-a",
)


responses = [
        JSONResponse(status_code=200, content={"message": "success"}),
        JSONResponse(status_code=404, content={"message": "The requested equipment is not found"}),
        JSONResponse(status_code=500, content={"message": "Internal provisioning exception"})
]


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
        },
        500: {
            "content": {
                "application/json": {
                    "example": {
                        "code": 500,
                        "message": "Internal provisioning exception"
                    }
                }
            },
            "description": "Внутренняя ошибка при конфигурации"
        }
    }
)
async def configure_device_by_id(
    body: ConfigurationRequest,
    id: str = Path(..., title="ID устройства", regex="^[a-zA-Z0-9]{6,}$"),
):
    await asyncio.sleep(60)
    return random.choice(responses)

