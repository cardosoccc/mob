"""Session model."""

import enum

from sqlalchemy import Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from mob.models.base import Base, TimestampMixin, generate_uuid


class SessionState(str, enum.Enum):
    PENDING = "pending"
    STARTING = "starting"
    IDLE = "idle"
    BUSY = "busy"
    FINISHED = "finished"
    FAILED = "failed"


class Session(Base, TimestampMixin):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    agent_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False
    )
    state: Mapped[SessionState] = mapped_column(
        Enum(SessionState), default=SessionState.PENDING, nullable=False
    )
    pod_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    task_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    agent: Mapped["Agent"] = relationship("Agent", back_populates="sessions")  # noqa: F821
    task: Mapped["Task | None"] = relationship("Task", back_populates="session")  # noqa: F821

    def __repr__(self) -> str:
        return f"<Session(id={self.id}, name={self.name}, state={self.state})>"
