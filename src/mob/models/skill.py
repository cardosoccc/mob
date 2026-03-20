"""Skill model."""

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from mob.models.base import Base, TimestampMixin, generate_uuid


class Skill(Base, TimestampMixin):
    __tablename__ = "skills"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    skills_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    references_path: Mapped[str | None] = mapped_column(String(500), nullable=True)

    def __repr__(self) -> str:
        return f"<Skill(id={self.id}, name={self.name})>"
