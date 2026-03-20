"""Group model."""

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from mob.models.base import Base, TimestampMixin, generate_uuid


class Group(Base, TimestampMixin):
    __tablename__ = "groups"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )

    organization: Mapped["Organization"] = relationship(  # noqa: F821
        "Organization", back_populates="groups"
    )
    members: Mapped[list["GroupMember"]] = relationship(
        "GroupMember", back_populates="group", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("name", "organization_id", name="uq_group_name_org"),
    )

    def __repr__(self) -> str:
        return f"<Group(id={self.id}, name={self.name})>"


class GroupMember(Base, TimestampMixin):
    __tablename__ = "group_members"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    group_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("groups.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    group: Mapped["Group"] = relationship("Group", back_populates="members")
    user: Mapped["User"] = relationship("User", back_populates="group_memberships")  # noqa: F821

    __table_args__ = (
        UniqueConstraint("group_id", "user_id", name="uq_group_member"),
    )
