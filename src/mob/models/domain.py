"""Domain model."""

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from mob.models.base import Base, TimestampMixin, generate_uuid


class Domain(Base, TimestampMixin):
    __tablename__ = "domains"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    identifier: Mapped[str] = mapped_column(String(200), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )

    organization: Mapped["Organization"] = relationship(  # noqa: F821
        "Organization", back_populates="domains"
    )
    agents: Mapped[list["Agent"]] = relationship(  # noqa: F821
        "Agent", back_populates="domain", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Domain(id={self.id}, identifier={self.identifier}, name={self.name})>"
