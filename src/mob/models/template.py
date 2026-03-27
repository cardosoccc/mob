"""Template model."""

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from mob.models.base import Base, TimestampMixin, generate_uuid


class Template(Base, TimestampMixin):
    __tablename__ = "templates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    image: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    runtime: Mapped[str] = mapped_column(String(50), nullable=False)
    capabilities: Mapped[str | None] = mapped_column(Text, nullable=True)
    resource_cpu_limit: Mapped[str | None] = mapped_column(String(20), nullable=True)
    resource_memory_limit: Mapped[str | None] = mapped_column(String(20), nullable=True)

    def __repr__(self) -> str:
        return f"<Template(id={self.id}, name={self.name})>"
