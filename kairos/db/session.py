from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from kairos.config import get_settings


def create_session_factory() -> async_sessionmaker[AsyncSession]:
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    return async_sessionmaker(engine, expire_on_commit=False)
