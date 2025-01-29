# Third party
import uuid
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import (Column,
                        Integer,
                        String,
                        ForeignKey
)
from sqlalchemy.dialects.postgresql import (
    UUID,
    ARRAY
)
__all__ = ["Base"]


class Base(DeclarativeBase):
    """
        Base class for all models
    """


class Configuration(Base):
    __tablename__ = "configurations"
    id = Column(Integer, primary_key=True)
    device_id = Column(String, nullable=False)
    timeout_in_seconds = Column(Integer, nullable=False)
    username = Column(String, nullable=False)
    password = Column(String, nullable=False)
    vlan = Column(Integer, nullable=True)
    interfaces = Column(ARRAY(Integer))


class Task(Base):
    __tablename__ = "tasks"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    configuration_id = Column(Integer, ForeignKey(Configuration.id), nullable=False)
    status = Column(String, nullable=False)