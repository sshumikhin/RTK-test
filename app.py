# Standart
import random
import time

# Third party
from fastapi import FastAPI, Path
from fastapi.responses import JSONResponse


# First party
from schema import ConfigurationRequest
from exceptions import ModelValidateError


app = FastAPI(
    title="service-a",
)


responses = [
        JSONResponse(status_code=200, content={"code": 200, "message": "success"}),
        JSONResponse(status_code=404, content={"code": 404, "message": "The requested equipment is not found"}),
        JSONResponse(status_code=500, content={"code": 500, "message": "Internal provisioning exception"})
]


@app.exception_handler(ModelValidateError)
def http_exception_handler(request, exc):
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
    body: ConfigurationRequest,
    id: str = Path(..., title="ID устройства", regex="^[a-zA-Z0-9]{6,}$"),
):
    # time.sleep(60)
    # return random.choice(responses)
    return responses[0]