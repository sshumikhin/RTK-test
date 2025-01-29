from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Any, Optional

from sqlalchemy.orm import selectinload

from postgres.models import Configuration, Task


async def create_configuration(
        session: AsyncSession,
        device_id: str,
        timeout_in_seconds: int,
        username: str,
        password: str,
        vlan: int,
        interfaces: List[int]
) -> Configuration:

    configuration = Configuration(
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


async def create_task(
        session: AsyncSession,
        configuration_id: int,
)-> Task:
    new_task = Task(
        configuration_id=configuration_id,
        status = "created"
    )

    session.add(new_task)
    await session.flush()
    return new_task


async def get_entity_by_params(
        model: Any,
        session: AsyncSession,
        conditions: List[Any] = None,
        load_relationships: Optional[List[Any]] = None,
        many=False,
        order_by: Any = None,
        offset: int = None,
        limit: int = None
) -> Any:

    query = select(model)

    if load_relationships is not None:
        for relationship in load_relationships:
            query = query.options(selectinload(relationship))

    if conditions is not None:
        query = query.where(*conditions)

    if order_by is not None:
        query = query.order_by(order_by)

    if offset is not None:
        query = query.offset(offset)

    if limit is not None:
        query = query.limit(limit)

    if many:
        result = (await session.execute(query)).scalars().all()
        return result

    result = (await session.execute(query)).scalar_one_or_none()
    return result
