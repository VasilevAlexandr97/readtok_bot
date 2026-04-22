from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    UUID as SA_UUID,
    BigInteger,
    DateTime,
)
from sqlalchemy.orm import Mapped, mapped_column

from readtok.infra.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(SA_UUID(as_uuid=True), primary_key=True)
    telegram_id: Mapped[int] = mapped_column(
        BigInteger,
        unique=True,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    def __str__(self) -> str:
        return (
            f"UserModel(id={self.id},"
            f"telegram_id={self.telegram_id}, "
            f"created_at={self.created_at}, "
            f"updated_at={self.updated_at})"
        )
