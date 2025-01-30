from typing import Optional, List
from pydantic import BaseModel, field_validator, constr, conint
from exceptions import ModelValidateError

class ConfigurationParameters(BaseModel):
    username: constr(min_length=1)
    password: constr(min_length=1)
    vlan: Optional[conint(ge=0)]
    interfaces: List[conint(ge=0)]

    @field_validator('interfaces', mode='before')
    @classmethod
    def validate_interfaces(cls, interfaces):
        if not interfaces:
            raise ModelValidateError("Interfaces list cannot be empty")
        return interfaces


class ConfigurationRequest(BaseModel):
    timeoutInSeconds: conint(ge=0)
    parameters: List[ConfigurationParameters]


    @field_validator("timeoutInSeconds", mode='before')
    @classmethod
    def validate_timeout(cls, timeout: int):
        if timeout < 0:
            raise ModelValidateError("Incorrect timeout value")
        return timeout

    @field_validator("parameters", mode='before')
    @classmethod
    def validate_parameters(cls, parameters):
        if not parameters:
            raise ModelValidateError("Parameters list cannot be empty")
        return parameters