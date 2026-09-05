import uuid

from sqlalchemy import Enum, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPKMixin
from app.models.enums import CompanyType


class Company(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "companies"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    company_type: Mapped[CompanyType] = mapped_column(
        Enum(CompanyType, name="company_type_enum"), nullable=False
    )
    industry: Mapped[str] = mapped_column(String(150), nullable=False)
    department: Mapped[str] = mapped_column(String(150), nullable=False)
    mission: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    # Owning student — this simulation instance belongs to one student.
    student_id: Mapped[str] = mapped_column(String(100), nullable=False)

    manager = relationship("Manager", back_populates="company", uselist=False, cascade="all, delete-orphan")
    projects = relationship("Project", back_populates="company", cascade="all, delete-orphan")
    team_members = relationship("TeamMember", back_populates="company", cascade="all, delete-orphan")
    simulations = relationship("Simulation", back_populates="company", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_companies_student_id", "student_id"),
        Index("ix_companies_company_type", "company_type"),
    )
