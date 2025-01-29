# Standart
from typing import Optional, List

# Third party
from pydantic import BaseModel, field_validator

# First party
from exceptions import ModelValidateError


class ConfigurationParameters(BaseModel):
    username: str
    password: str
    vlan: Optional[int]
    interfaces: List[int]


class ConfigurationRequest(BaseModel):
    timeoutInSeconds: int
    parameters: List[ConfigurationParameters]

    @field_validator("timeoutInSeconds", mode='before')
    @classmethod
    def validate_timeout(cls, timeout: int):
        if timeout < 0 or timeout > 14:
            raise ModelValidateError("Incorrect timeout value")
        return timeout
