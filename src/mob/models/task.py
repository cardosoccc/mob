"""Task model."""

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from mob.models.base import Base, TimestampMixin, generate_uuid


class Task(Base, TimestampMixin):
    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    instruction: Mapped[str] = mapped_column(Text, nullable=False)
    definition_of_done: Mapped[str | None] = mapped_column(Text, nullable=True)
    agent_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False
    )

    agent: Mapped["Agent"] = relationship("Agent")  # noqa: F821
    session: Mapped["Session | None"] = relationship(  # noqa: F821
        "Session", back_populates="task", uselist=False
    )

    def __repr__(self) -> str:
        return f"<Task(id={self.id})>"
