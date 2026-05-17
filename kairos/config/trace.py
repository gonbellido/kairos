import uuid
from contextvars import ContextVar

_trace_id: ContextVar[str] = ContextVar("trace_id", default="")
_session_id: ContextVar[str] = ContextVar("session_id", default="")
_profile_id: ContextVar[str] = ContextVar("profile_id", default="")
_coach_id: ContextVar[str] = ContextVar("coach_id", default="")


def generate_trace_id() -> str:
    return uuid.uuid4().hex[:12]


class TraceContext:
    """Context manager and accessor for structured log context."""

    def __init__(
        self,
        trace_id: str = "",
        session_id: str = "",
        profile_id: str = "",
        coach_id: str = "",
    ):
        self.trace_id = trace_id or generate_trace_id()
        self.session_id = session_id
        self.profile_id = profile_id
        self.coach_id = coach_id

    def __enter__(self):
        self._token_trace = _trace_id.set(self.trace_id)
        self._token_session = _session_id.set(self.session_id)
        self._token_profile = _profile_id.set(self.profile_id)
        self._token_coach = _coach_id.set(self.coach_id)
        return self

    def __exit__(self, *args):
        _trace_id.reset(self._token_trace)
        _session_id.reset(self._token_session)
        _profile_id.reset(self._token_profile)
        _coach_id.reset(self._token_coach)

    @staticmethod
    def get_trace_id() -> str:
        return _trace_id.get()

    @staticmethod
    def get_session_id() -> str:
        return _session_id.get()

    @staticmethod
    def get_profile_id() -> str:
        return _profile_id.get()

    @staticmethod
    def get_coach_id() -> str:
        return _coach_id.get()

    @staticmethod
    def snapshot() -> dict:
        d = {}
        t = _trace_id.get()
        if t:
            d["trace_id"] = t
        s = _session_id.get()
        if s:
            d["session_id"] = s
        p = _profile_id.get()
        if p:
            d["profile_id"] = p
        c = _coach_id.get()
        if c:
            d["coach_id"] = c
        return d
