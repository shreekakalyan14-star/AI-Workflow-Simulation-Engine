from sqlalchemy import String, ForeignKey, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import UUIDPKMixin, TimestampMixin
from app.models.enums import InternshipStatus


class Internship(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "internships"

    student_id: Mapped[str] = mapped_column(String(100), nullable=False)

    company_id: Mapped[str] = mapped_column(
        ForeignKey("companies.id"),
        nullable=True
    )

    current_project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id"),
        nullable=True
    )

    status: Mapped[InternshipStatus] = mapped_column(
        Enum(InternshipStatus),
        default=InternshipStatus.ACTIVE,
        nullable=False,
    )

    company = relationship("Company")
    project = relationship("Project")