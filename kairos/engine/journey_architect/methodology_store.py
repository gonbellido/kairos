import logging
import secrets
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from kairos.db.models import CoachMethodologyDocModel

logger = logging.getLogger(__name__)

class CoachMethodologyStore:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self._sf = session_factory

    async def save_methodology(self, coach_id: str, content: str, title: str = "", source: str = "text") -> str:
        doc_id = secrets.token_hex(8)
        async with self._sf() as session:
            doc = CoachMethodologyDocModel(
                id=doc_id,
                coach_id=coach_id,
                title=title,
                content=content,
                source=source
            )
            session.add(doc)
            await session.commit()
            return doc_id

    async def get_methodology(self, coach_id: str) -> str:
        """Returns all methodology content concatenated for LLM context."""
        async with self._sf() as session:
            result = await session.execute(
                select(CoachMethodologyDocModel)
                .where(CoachMethodologyDocModel.coach_id == coach_id)
                .order_by(CoachMethodologyDocModel.created_at.asc())
            )
            docs = result.scalars().all()
            return "\n\n".join([f"--- {doc.title} ---\n{doc.content}" for doc in docs])

    async def list_methodology_docs(self, coach_id: str) -> list[dict]:
        async with self._sf() as session:
            result = await session.execute(
                select(CoachMethodologyDocModel)
                .where(CoachMethodologyDocModel.coach_id == coach_id)
                .order_by(CoachMethodologyDocModel.created_at.desc())
            )
            docs = result.scalars().all()
            return [
                {
                    "id": d.id,
                    "title": d.title,
                    "source": d.source,
                    "created_at": d.created_at.isoformat() if d.created_at else ""
                }
                for d in docs
            ]

    async def delete_doc(self, coach_id: str, doc_id: str) -> bool:
        async with self._sf() as session:
            result = await session.execute(
                delete(CoachMethodologyDocModel)
                .where(CoachMethodologyDocModel.id == doc_id, CoachMethodologyDocModel.coach_id == coach_id)
            )
            await session.commit()
            return result.rowcount > 0
