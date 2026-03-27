"""Agent model."""

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from mob.models.base import Base, TimestampMixin, generate_uuid


class Agent(Base, TimestampMixin):
    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    agent_template: Mapped[str] = mapped_column(String(500), nullable=False)
    model_endpoint: Mapped[str | None] = mapped_column(String(500), nullable=True)
    env_defaults: Mapped[str | None] = mapped_column(Text, nullable=True)
    custom_config: Mapped[str | None] = mapped_column(Text, nullable=True)
    domain_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("domains.id", ondelete="CASCADE"), nullable=False
    )

    domain: Mapped["Domain"] = relationship("Domain", back_populates="agents")  # noqa: F821
    sessions: Mapped[list["Session"]] = relationship(  # noqa: F821
        "Session", back_populates="agent", cascade="all, delete-orphan"
    )
    skills: Mapped[list["AgentSkill"]] = relationship(
        "AgentSkill", back_populates="agent", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Agent(id={self.id}, name={self.name})>"


class AgentSkill(Base):
    __tablename__ = "agent_skills"

    agent_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("agents.id", ondelete="CASCADE"), primary_key=True
    )
    skill_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("skills.id", ondelete="CASCADE"), primary_key=True
    )

    agent: Mapped["Agent"] = relationship("Agent", back_populates="skills")
    skill: Mapped["Skill"] = relationship("Skill")  # noqa: F821
