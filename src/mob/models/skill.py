"""Skill model."""

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from mob.models.base import Base, TimestampMixin, generate_uuid


class Skill(Base, TimestampMixin):
    __tablename__ = "skills"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    description: Mapped[str] = mapped_column(String(1024), nullable=False)
    skill_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    license: Mapped[str | None] = mapped_column(String(255), nullable=True)
    compatibility: Mapped[str | None] = mapped_column(String(500), nullable=True)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    allowed_tools: Mapped[str | None] = mapped_column(String(500), nullable=True)

    def __repr__(self) -> str:
        return f"<Skill(id={self.id}, name={self.name})>"
