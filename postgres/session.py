from typing import Any

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from utils import getenv

__all__ = ["async_session"]


class Session:
    HOST = getenv("DB_HOST")
    PORT = getenv("DB_PORT")
    NAME = getenv("DB_NAME")
    USER = getenv("DB_USER")
    PASSWORD = getenv("DB_PASS")
    ASYNC_CONNECTION_URL = f"postgresql+asyncpg://{USER}:{PASSWORD}@{HOST}:{PORT}/{NAME}"

    def __init__(self):
        bind: Any = create_async_engine(
            url=self.ASYNC_CONNECTION_URL,
            future=True,
            echo=False
        )

        self.async_session = sessionmaker(
            bind=bind,
            expire_on_commit=False,
            class_=AsyncSession,
        )

    async def __call__(self):
        async with self.async_session() as session:
            try:
                yield session
            finally:
                await session.close()

    async def get_session(self):
        return self.async_session


async_session = Session()
