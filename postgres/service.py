from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Any, Optional

from sqlalchemy.orm import selectinload

from postgres.models import ConfigurationTask


async def create_equipment_configuration(
        session: AsyncSession,
        device_id: str,
        timeout_in_seconds: int,
        username: str,
        password: str,
        vlan: int,
        interfaces: List[int]
) -> ConfigurationTask:

    configuration = ConfigurationTask(
        device_id=device_id,
        timeout_in_seconds=timeout_in_seconds,
        username=username,
        password=password,
        vlan=vlan,
        interfaces=interfaces
    )

    session.add(configuration)
    await session.flush()
    return configuration


async def get_task_by_id(
        session: AsyncSession,
        task_id: str
) -> Optional[ConfigurationTask]:

    query = select(
        ConfigurationTask
    ).where(
        ConfigurationTask.task_id == task_id
    )

    result = (await session.execute(query)).scalar_one_or_none()

    return result
