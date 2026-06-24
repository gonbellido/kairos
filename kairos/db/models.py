from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, Boolean, Float, DateTime, JSON, Integer, ForeignKey
from sqlalchemy.orm import DeclarativeBase

_utcnow = lambda: datetime.now(tz=timezone.utc)


class Base(DeclarativeBase):
    pass


class ProfileModel(Base):
    __tablename__ = "profiles"
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(Text, default="")
    version = Column(String, default="0.1.0")
    active = Column(Boolean, default=True)
    system_prompt_template = Column(Text, default="")
    default_impronta = Column(JSON, default=dict)
    impronta_constraints = Column(JSON, nullable=True)
    plugins = Column(JSON, default=list)
    tags = Column(JSON, default=list)
    created_at = Column(DateTime(timezone=True), default=lambda: _utcnow())
    updated_at = Column(DateTime(timezone=True), default=lambda: _utcnow(), onupdate=lambda: _utcnow())


class SessionModel(Base):
    __tablename__ = "sessions"
    id = Column(String, primary_key=True)
    profile_id = Column(String, nullable=False)
    user_id = Column(String, nullable=False)
    context = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), default=lambda: _utcnow())
    updated_at = Column(DateTime(timezone=True), default=lambda: _utcnow(), onupdate=lambda: _utcnow())


class CoachModel(Base):
    __tablename__ = "coaches"
    id = Column(String, primary_key=True)
    email = Column(String, unique=True, nullable=False, index=True)
    name = Column(String, nullable=False)
    role = Column(String, default="coach")
    plan = Column(String, default="free")
    language = Column(String, default="es")
    telegram_token = Column(String, default="")
    telegram_chat_id = Column(String, default="")
    telegram_bot_name = Column(String, default="")
    impronta_data = Column(JSON, default=dict)
    notification_settings = Column(JSON, default=dict)
    onboarding_meta = Column(JSON, default=dict)
    profile_data = Column(JSON, default=dict)
    default_journey_id = Column(String, default="")
    voice_default_journey_id = Column(String, default="")

    password_hash = Column(String, nullable=False)
    salt = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: _utcnow())


class CoachSessionModel(Base):
    __tablename__ = "coach_sessions"
    token = Column(String, primary_key=True)
    coach_id = Column(String, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=lambda: _utcnow())


class AgentPromptModel(Base):
    __tablename__ = "agent_prompts"
    id = Column(String, primary_key=True)
    agent = Column(String, nullable=False, unique=True, index=True)
    description = Column(String, default="")
    prompt_template = Column(Text, nullable=False)
    lang = Column(String, default="es")
    created_at = Column(DateTime(timezone=True), default=lambda: _utcnow())
    updated_at = Column(DateTime(timezone=True), default=lambda: _utcnow(), onupdate=lambda: _utcnow())


# ── Fase I: Journey System ──

class JourneyModel(Base):
    __tablename__ = "journeys"
    id = Column(String, primary_key=True)
    coach_id = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, default="")
    objective = Column(Text, default="")
    profile_type = Column(String, default="custom")
    language = Column(String, default="es")
    status = Column(String, default="draft")
    tag_mappings = Column(JSON, default=dict)
    version = Column(Integer, default=1)
    channel = Column(String, default="text")  # text, voice, both
    created_at = Column(DateTime(timezone=True), default=lambda: _utcnow())
    updated_at = Column(DateTime(timezone=True), default=lambda: _utcnow(), onupdate=lambda: _utcnow())


class JourneyPhaseModel(Base):
    __tablename__ = "journey_phases"
    id = Column(String, primary_key=True)
    journey_id = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, default="")
    objective = Column(Text, default="")
    order_index = Column(Integer, default=0)
    completion_criteria = Column(Text, default="")
    visible_to_client = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: _utcnow())
    updated_at = Column(DateTime(timezone=True), default=lambda: _utcnow(), onupdate=lambda: _utcnow())


class JourneyAgentModel(Base):
    __tablename__ = "journey_agents"
    id = Column(String, primary_key=True)
    journey_id = Column(String, nullable=False, index=True)
    phase_id = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False)
    role = Column(String, default="")
    goal = Column(Text, default="")
    system_prompt = Column(Text, default="")
    instructions = Column(Text, default="")
    order_index = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    allowed_tags = Column(JSON, default=list)
    output_schema = Column(JSON, default=dict)
    collects_fields = Column(JSON, default=list)
    tag_mappings = Column(JSON, default=dict)
    version = Column(Integer, default=1)
    updated_at = Column(DateTime(timezone=True), default=lambda: _utcnow(), onupdate=lambda: _utcnow())


class ClientJourneyModel(Base):
    __tablename__ = "client_journeys"
    id = Column(String, primary_key=True)
    client_id = Column(String, nullable=False, index=True)
    coach_id = Column(String, nullable=False, index=True)
    journey_id = Column(String, nullable=False)
    current_phase_id = Column(String, nullable=True)
    current_agent_id = Column(String, nullable=True)
    status = Column(String, default="not_started")
    progress_pct = Column(Integer, default=0)
    collected_data = Column(JSON, default=dict)
    current_phase_order = Column(Integer, default=1)
    turn_count = Column(Integer, default=0)
    objective_state = Column(JSON, default=dict)
    extra = Column(JSON, default=dict)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    last_interaction_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: _utcnow())
    updated_at = Column(DateTime(timezone=True), default=lambda: _utcnow(), onupdate=lambda: _utcnow())


class ClientSharedProfileModel(Base):
    __tablename__ = "client_shared_profiles"
    id = Column(String, primary_key=True)
    client_id = Column(String, nullable=False, unique=True, index=True)
    coach_id = Column(String, nullable=False, index=True)
    journey_id = Column(String, nullable=True)
    profile_data = Column(JSON, default=dict)
    goals_data = Column(JSON, default=dict)
    insights_data = Column(JSON, default=list)
    blockers_data = Column(JSON, default=list)
    tasks_data = Column(JSON, default=list)
    checkpoints_data = Column(JSON, default=list)
    conversation_summary = Column(Text, default="")
    risk_flags_data = Column(JSON, default=list)
    created_at = Column(DateTime(timezone=True), default=lambda: _utcnow())
    updated_at = Column(DateTime(timezone=True), default=lambda: _utcnow(), onupdate=lambda: _utcnow())


class JourneyEventModel(Base):
    __tablename__ = "journey_events"
    id = Column(String, primary_key=True)
    client_id = Column(String, nullable=False, index=True)
    coach_id = Column(String, nullable=False)
    journey_id = Column(String, nullable=True)
    phase_id = Column(String, nullable=True)
    agent_id = Column(String, nullable=True)
    event_type = Column(String, nullable=False)
    payload_data = Column(JSON, default=dict)
    trace_id = Column(String, default="")
    created_at = Column(DateTime(timezone=True), default=lambda: _utcnow())

class CoachMethodologyDocModel(Base):
    __tablename__ = "coach_methodology_docs"
    id = Column(String, primary_key=True)
    coach_id = Column(String, ForeignKey("coaches.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String, nullable=False, default="")
    content = Column(Text, nullable=False)
    source = Column(String, default="text")
    created_at = Column(DateTime(timezone=True), default=lambda: _utcnow())
