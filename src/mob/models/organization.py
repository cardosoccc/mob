"""Organization model."""

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from mob.models.base import Base, TimestampMixin, generate_uuid


class Organization(Base, TimestampMixin):
    __tablename__ = "organizations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    identifier: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    domains: Mapped[list["Domain"]] = relationship(  # noqa: F821
        "Domain", back_populates="organization", cascade="all, delete-orphan"
    )
    groups: Mapped[list["Group"]] = relationship(  # noqa: F821
        "Group", back_populates="organization", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Organization(id={self.id}, identifier={self.identifier}, name={self.name})>"
