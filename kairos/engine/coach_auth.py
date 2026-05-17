import json
import hashlib
import secrets
from datetime import datetime, timezone
from pathlib import Path

_utcnow = lambda: datetime.now(tz=timezone.utc)

DB_PATH = Path(__file__).parent.parent / "kairos_coaches.json"


class CoachDB:
    def __init__(self):
        self._db = self._load()

    def _load(self) -> dict:
        if DB_PATH.exists():
            return json.loads(DB_PATH.read_text())
        return {"coaches": [], "sessions": {}}

    def _save(self):
        DB_PATH.write_text(json.dumps(self._db, indent=2, default=str))

    def create_coach(self, email: str, password: str, name: str, role: str = "coach") -> dict:
        existing = [c for c in self._db["coaches"] if c["email"] == email]
        if existing:
            raise ValueError("Email already registered")

        salt = secrets.token_hex(16)
        pwd_hash = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100000).hex()

        coach = {
            "id": secrets.token_hex(8),
            "email": email,
            "name": name,
            "role": role,
            "password_hash": pwd_hash,
            "salt": salt,
            "created_at": _utcnow().isoformat(),
        }
        self._db["coaches"].append(coach)
        self._save()
        return {"id": coach["id"], "email": coach["email"], "name": coach["name"], "role": coach["role"]}

    def authenticate(self, email: str, password: str) -> dict | None:
        for c in self._db["coaches"]:
            if c["email"] == email:
                pwd_hash = hashlib.pbkdf2_hmac("sha256", password.encode(), c["salt"].encode(), 100000).hex()
                if pwd_hash == c["password_hash"]:
                    return {"id": c["id"], "email": c["email"], "name": c["name"], "role": c["role"]}
        return None

    def get_by_id(self, coach_id: str) -> dict | None:
        for c in self._db["coaches"]:
            if c["id"] == coach_id:
                return {"id": c["id"], "email": c["email"], "name": c["name"], "role": c["role"]}
        return None

    def list_coaches(self) -> list[dict]:
        return [{"id": c["id"], "email": c["email"], "name": c["name"], "role": c["role"], "created_at": c.get("created_at", "")} for c in self._db["coaches"]]

    def delete_coach(self, coach_id: str) -> bool:
        before = len(self._db["coaches"])
        self._db["coaches"] = [c for c in self._db["coaches"] if c["id"] != coach_id]
        if len(self._db["coaches"]) < before:
            self._save()
            return True
        return False

    def create_session(self, coach_id: str) -> str:
        token = secrets.token_hex(32)
        self._db["sessions"][token] = {"coach_id": coach_id, "created_at": _utcnow().isoformat()}
        self._save()
        return token

    def get_session(self, token: str) -> dict | None:
        # Re-read from file in case another instance wrote sessions
        self._db = self._load()
        session = self._db["sessions"].get(token)
        if session:
            return self.get_by_id(session["coach_id"])
        return None

    def delete_session(self, token: str):
        self._db["sessions"].pop(token, None)
        self._save()

    def seed_defaults(self):
        if not self._db["coaches"]:
            self.create_coach("admin@kairos.app", "admin123", "Admin", role="admin")
            self.create_coach("coach@kairos.app", "coach123", "Coach Demo", role="coach")
            print("✅ Coaches seeded: admin@kairos.app / coach@kairos.app")
