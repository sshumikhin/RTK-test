# Standart
import random
import time
from contextlib import asynccontextmanager

# Third party
from fastapi import FastAPI, Path, Request
from fastapi.responses import JSONResponse


# First party
from schema import ConfigurationRequest
from exceptions import ModelValidateError
import logging

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Запуск сервиса А")
    yield
    logger.info("Остановка сервиса А")


app = FastAPI(
    title="service-a",
    lifespan=lifespan
)


logger = logging.getLogger("Service A")
logger.setLevel(logging.INFO)


responses = [
 JSONResponse(
     status_code=200,
     content={
         "code": 200, "message": "success"
     }
 ),
 JSONResponse(
     status_code=404,
     content={
         "code": 404, "message": "The requested equipment is not found"
     }
 ),
 JSONResponse(
     status_code=500,
     content={
         "code": 500,
         "message": "Internal provisioning exception"
     }
 )
]


@app.exception_handler(ModelValidateError)
def http_exception_handler(_: Request, exc):
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
def configure_device_by_id(
    _: ConfigurationRequest,
    id: str = Path(..., title="ID устройства", regex="^[a-zA-Z0-9]{6,}$"),
):
    logger.info(f"Конфигурация устройства {id}")
    time.sleep(60)
    return random.choice(responses)


@app.get("/health", include_in_schema=False)
def health_check():
    return {"status": "healthy"}