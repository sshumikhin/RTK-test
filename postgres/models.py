# Third party
import uuid

from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import Column, Integer, String
from sqlalchemy.dialects.postgresql import (
    UUID,
    ARRAY
)
__all__ = ["Base"]


class Base(DeclarativeBase):
    """
        Base class for all models
    """


class ConfigurationTask(Base):
    __tablename__ = "configuration_tasks"
    task_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, unique=True)
    device_id = Column(String, nullable=False)
    timeout_in_seconds = Column(Integer, nullable=False)
    username = Column(String, nullable=False)
    password = Column(String, nullable=False)
    vlan = Column(Integer, nullable=True),
    interfaces = Column(ARRAY(Integer))
    status = Column(String, nullable=False)

