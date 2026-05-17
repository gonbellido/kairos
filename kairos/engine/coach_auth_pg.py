import hashlib
import logging
import secrets
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, delete, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from kairos.db.models import CoachModel, CoachSessionModel

_utcnow = lambda: datetime.now(tz=timezone.utc)
logger = logging.getLogger(__name__)


class CoachDBA:
    """Auth de coaches en PostgreSQL."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self._sf = session_factory

    def _to_dict(self, c: CoachModel) -> dict:
        return {
            "id": c.id, "email": c.email, "name": c.name,
            "role": c.role, "plan": c.plan,
            "language": getattr(c, "language", "es"),
            "telegram_token": getattr(c, "telegram_token", ""),
            "telegram_chat_id": getattr(c, "telegram_chat_id", ""),
            "telegram_bot_name": getattr(c, "telegram_bot_name", ""),
            "impronta": getattr(c, "impronta_data", None) or {},
            "notification_settings": getattr(c, "notification_settings", None) or {},
            "onboarding_meta": getattr(c, "onboarding_meta", None) or {},
            "profile_data": getattr(c, "profile_data", None) or {},
            "default_journey_id": getattr(c, "default_journey_id", ""),
            "created_at": c.created_at.isoformat() if c.created_at else "",
        }

    async def create_coach(self, email: str, password: str, name: str,
                           role: str = "coach", plan: str = "free", language: str = "es") -> dict:
        async with self._sf() as session:
            existing = (await session.execute(
                select(CoachModel).where(CoachModel.email == email)
            )).scalar_one_or_none()
            if existing:
                raise ValueError("Email already registered")

            salt = secrets.token_hex(16)
            pwd_hash = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100000).hex()

            coach = CoachModel(
                id=secrets.token_hex(8),
                email=email, name=name, role=role, plan=plan, language=language,
                password_hash=pwd_hash, salt=salt,
            )
            session.add(coach)
            await session.commit()
            return self._to_dict(coach)

    async def update_coach(self, coach_id: str, **fields) -> dict | None:
        async with self._sf() as session:
            coach = await session.get(CoachModel, coach_id)
            if not coach:
                return None

            allowed = {"name", "email", "role", "plan", "language", "telegram_token", "telegram_chat_id", "telegram_bot_name", "impronta_data", "notification_settings", "onboarding_meta", "profile_data", "default_journey_id"}
            for key, value in fields.items():
                if key in allowed and value is not None:
                    setattr(coach, key, value)

            if "password" in fields and fields["password"]:
                salt = secrets.token_hex(16)
                coach.salt = salt
                coach.password_hash = hashlib.pbkdf2_hmac(
                    "sha256", fields["password"].encode(), salt.encode(), 100000
                ).hex()

            await session.commit()
            await session.refresh(coach)
            return self._to_dict(coach)

    async def authenticate(self, email: str, password: str) -> dict | None:
        async with self._sf() as session:
            coach = (await session.execute(
                select(CoachModel).where(CoachModel.email == email)
            )).scalar_one_or_none()
            if not coach:
                return None
            pwd_hash = hashlib.pbkdf2_hmac("sha256", password.encode(), coach.salt.encode(), 100000).hex()
            if pwd_hash != coach.password_hash:
                return None
            return self._to_dict(coach)

    async def get_by_id(self, coach_id: str) -> dict | None:
        async with self._sf() as session:
            coach = await session.get(CoachModel, coach_id)
            return self._to_dict(coach) if coach else None

    async def list_coaches(self) -> list[dict]:
        async with self._sf() as session:
            result = await session.execute(select(CoachModel).order_by(CoachModel.created_at.desc()))
            return [self._to_dict(c) for c in result.scalars().all()]

    async def delete_coach(self, coach_id: str) -> bool:
        async with self._sf() as session:
            coach = await session.get(CoachModel, coach_id)
            if not coach:
                return False
            await session.delete(coach)
            await session.commit()
            return True

    async def create_session(self, coach_id: str) -> str:
        token = secrets.token_hex(32)
        async with self._sf() as session:
            sess = CoachSessionModel(token=token, coach_id=coach_id)
            session.add(sess)
            await session.commit()
            return token

    async def get_session(self, token: str) -> dict | None:
        async with self._sf() as session:
            cs = await session.get(CoachSessionModel, token)
            if not cs:
                return None
            coach = await session.get(CoachModel, cs.coach_id)
            return self._to_dict(coach) if coach else None

    async def delete_session(self, token: str):
        async with self._sf() as session:
            await session.execute(
                delete(CoachSessionModel).where(CoachSessionModel.token == token)
            )
            await session.commit()

    async def seed_defaults(self):
        async with self._sf() as session:
            count = (await session.execute(select(CoachModel))).scalars().all()
            if not count:
                await session.close()
                await self.create_coach("admin@kairos.app", "admin123", "Admin", role="admin", plan="admin", language="es")
                await self.create_coach("coach@kairos.app", "coach123", "Coach Demo", role="coach", plan="pro", language="es")
                logger.info("Coaches seeded: admin@kairos.app / coach@kairos.app")
