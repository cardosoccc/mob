"""AgentRun model."""

import enum

from sqlalchemy import Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from mob.models.base import Base, TimestampMixin, generate_uuid


class AgentRunState(str, enum.Enum):
    PENDING = "pending"
    STARTING = "starting"
    IDLE = "idle"
    BUSY = "busy"
    FINISHED = "finished"
    FAILED = "failed"


class AgentRun(Base, TimestampMixin):
    __tablename__ = "agent_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    agent_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False
    )
    state: Mapped[AgentRunState] = mapped_column(
        Enum(AgentRunState), default=AgentRunState.PENDING, nullable=False
    )
    pod_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    task_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    agent: Mapped["Agent"] = relationship("Agent", back_populates="runs")  # noqa: F821
    task: Mapped["Task | None"] = relationship("Task", back_populates="agent_run")  # noqa: F821

    def __repr__(self) -> str:
        return f"<AgentRun(id={self.id}, state={self.state})>"
