from datetime import datetime, timezone
from uuid import uuid4
from typing import Any

from pydantic import BaseModel, Field

_utcnow = lambda: datetime.now(tz=timezone.utc)


class Session(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    coach_id: str = ""
    client_id: str = ""
    profile_id: str = ""
    status: str = "active"  # active | paused | closed
    message_count: int = 0
    summary: str = ""
    tags: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: _utcnow())
    updated_at: datetime = Field(default_factory=lambda: _utcnow())
    closed_at: datetime | None = None


class SessionManager:
    _sessions: dict[str, Session] = {}

    def start(self, coach_id: str, client_id: str = "", profile_id: str = "") -> Session:
        session = Session(
            coach_id=coach_id,
            client_id=client_id,
            profile_id=profile_id,
        )
        self._sessions[session.id] = session
        return session

    def get(self, session_id: str) -> Session | None:
        return self._sessions.get(session_id)

    def touch(self, session_id: str) -> None:
        session = self._sessions.get(session_id)
        if session:
            session.message_count += 1
            session.updated_at = _utcnow()

    def close(self, session_id: str, summary: str = "") -> Session | None:
        session = self._sessions.get(session_id)
        if session:
            session.status = "closed"
            session.summary = summary
            session.closed_at = _utcnow()
        return session

    def list_active(self, coach_id: str) -> list[Session]:
        return [s for s in self._sessions.values()
                if s.coach_id == coach_id and s.status == "active"]

    def list_by_client(self, client_id: str) -> list[Session]:
        return [s for s in self._sessions.values()
                if s.client_id == client_id]
