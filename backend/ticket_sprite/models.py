"""ORM models. Vocabulary follows CONTEXT.md."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from enum import StrEnum

from sqlalchemy import JSON, Boolean, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def _uuid() -> str:
    return uuid.uuid4().hex


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Role(StrEnum):
    PM = "pm"
    FAE = "fae"
    RD = "rd"


class RequestType(StrEnum):
    FEATURE = "feature"
    BUG = "bug"
    TASK = "task"


class InterviewStatus(StrEnum):
    INTERVIEWING = "interviewing"
    SPEC_DRAFT = "spec_draft"
    TICKETED = "ticketed"
    DECISION_RECORD = "decision_record"


class QuestionKind(StrEnum):
    QUESTION = "question"
    PREMISE = "premise"


class QuestionStatus(StrEnum):
    PENDING = "pending"
    ANSWERED = "answered"  # Answer
    UNKNOWN = "unknown"  # -> Open Question
    SKIPPED = "skipped"  # -> Assumption
    CONFIRMED = "confirmed"  # Premise confirmed
    CORRECTED = "corrected"  # Premise corrected
    WITHDRAWN = "withdrawn"  # removed by the Requester before it was answered

    @property
    def resolved(self) -> bool:
        return self is not QuestionStatus.PENDING


class HandoffStatus(StrEnum):
    OPEN = "open"
    COMPLETED = "completed"
    RECALLED = "recalled"


class User(Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), primary_key=True)
    observ_id: Mapped[int | None] = mapped_column(Integer)
    display_name: Mapped[str | None] = mapped_column(String(200))
    default_role: Mapped[str] = mapped_column(String(8), default=Role.PM)
    # True once they picked it in Settings; until then USER_ROLES sets it at each login
    default_role_chosen: Mapped[bool | None] = mapped_column(Boolean)
    # ADO Credential (v1: PAT, Fernet-encrypted)
    ado_pat_encrypted: Mapped[str | None] = mapped_column(Text)
    ado_display_name: Mapped[str | None] = mapped_column(String(200))
    ado_pat_expires_on: Mapped[date | None] = mapped_column(Date)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Interview(Base):
    __tablename__ = "interviews"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    requester_email: Mapped[str] = mapped_column(String(320), index=True)
    role: Mapped[str] = mapped_column(String(8))
    product: Mapped[str] = mapped_column(String(64), default="middleware")
    request_type: Mapped[str] = mapped_column(String(16))
    template: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), default=InterviewStatus.INTERVIEWING)
    request_text: Mapped[str] = mapped_column(Text)
    round: Mapped[int] = mapped_column(Integer, default=0)
    # Question Budget: most questions this Interview may ask; None = no limit
    question_budget: Mapped[int | None] = mapped_column(Integer)
    # Audience: the Role the Spec is written for; None (older rows) = default_audience(role)
    audience: Mapped[str | None] = mapped_column(String(8))
    # Assignee: who the Ticket is assigned to in ADO, if the Requester named someone
    assignee_email: Mapped[str | None] = mapped_column(String(320))
    engine_done: Mapped[bool] = mapped_column(Boolean, default=False)
    engine_busy: Mapped[bool] = mapped_column(Boolean, default=False)
    engine_summary: Mapped[str | None] = mapped_column(Text)
    engine_error: Mapped[str | None] = mapped_column(Text)
    new_terms: Mapped[list] = mapped_column(JSON, default=list)

    title: Mapped[str | None] = mapped_column(String(255))
    spec_markdown: Mapped[str | None] = mapped_column(Text)
    # A regenerated Spec for an Interview already ticketed, waiting to replace the ADO description
    spec_revision: Mapped[str | None] = mapped_column(Text)
    suggested_priority: Mapped[int | None] = mapped_column(Integer)
    suggested_severity: Mapped[str | None] = mapped_column(String(32))
    frozen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    ticket_id: Mapped[int | None] = mapped_column(Integer)
    ticket_url: Mapped[str | None] = mapped_column(String(500))
    ticket_type: Mapped[str | None] = mapped_column(String(32))  # ADO work item type the Ticket was opened as
    parent_id: Mapped[int | None] = mapped_column(Integer)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    questions: Mapped[list[Question]] = relationship(
        back_populates="interview", order_by="(Question.round, Question.seq)", cascade="all, delete-orphan"
    )
    attachments: Mapped[list[Attachment]] = relationship(back_populates="interview", cascade="all, delete-orphan")
    handoffs: Mapped[list[Handoff]] = relationship(back_populates="interview", cascade="all, delete-orphan")


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    interview_id: Mapped[str] = mapped_column(ForeignKey("interviews.id"), index=True)
    round: Mapped[int] = mapped_column(Integer)
    seq: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(16), default=QuestionKind.QUESTION)
    title: Mapped[str] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(Text)
    options: Mapped[list] = mapped_column(JSON, default=list)
    recommendation: Mapped[str | None] = mapped_column(Text)
    rationale: Mapped[str | None] = mapped_column(Text)
    ai_note: Mapped[str | None] = mapped_column(Text)  # e.g. Premise verification against the Knowledge Source
    core: Mapped[bool] = mapped_column(Boolean, default=False)

    respondent_email: Mapped[str] = mapped_column(String(320), index=True)
    handoff_id: Mapped[str | None] = mapped_column(ForeignKey("handoffs.id"))
    status: Mapped[str] = mapped_column(String(16), default=QuestionStatus.PENDING)
    answer_text: Mapped[str | None] = mapped_column(Text)
    answered_by: Mapped[str | None] = mapped_column(String(320))
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    interview: Mapped[Interview] = relationship(back_populates="questions")
    handoff: Mapped[Handoff | None] = relationship(back_populates="questions")


class Handoff(Base):
    __tablename__ = "handoffs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    interview_id: Mapped[str] = mapped_column(ForeignKey("interviews.id"), index=True)
    from_email: Mapped[str] = mapped_column(String(320))
    to_email: Mapped[str] = mapped_column(String(320), index=True)
    status: Mapped[str] = mapped_column(String(16), default=HandoffStatus.OPEN)
    reminders_sent: Mapped[int] = mapped_column(Integer, default=0)
    requester_alerted: Mapped[bool] = mapped_column(Boolean, default=False)
    last_notified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    interview: Mapped[Interview] = relationship(back_populates="handoffs")
    questions: Mapped[list[Question]] = relationship(back_populates="handoff")


class Attachment(Base):
    __tablename__ = "attachments"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    interview_id: Mapped[str] = mapped_column(ForeignKey("interviews.id"), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(128))
    size: Mapped[int] = mapped_column(Integer)
    storage_path: Mapped[str] = mapped_column(String(500))
    uploaded_by: Mapped[str] = mapped_column(String(320))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    interview: Mapped[Interview] = relationship(back_populates="attachments")


class GameBest(Base):
    """Someone's all-time best in one of the waiting games, for its leaderboard."""

    __tablename__ = "game_bests"

    game: Mapped[str] = mapped_column(String(16), primary_key=True)  # firefly | mines
    email: Mapped[str] = mapped_column(String(320), primary_key=True)
    best: Mapped[int] = mapped_column(Integer)  # firefly: words collected; mines: milliseconds to clear
    achieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
