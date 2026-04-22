from uuid import UUID

from sqlalchemy import (
    UUID as SA_UUID,
    ForeignKey,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from readtok.infra.db.base import Base


class BookCategory(Base):
    __tablename__ = "book_categories"

    id: Mapped[UUID] = mapped_column(SA_UUID(as_uuid=True), primary_key=True)
    name: Mapped[str] = mapped_column(nullable=False, unique=True)

    def __repr__(self) -> str:
        return f"BookCategory(id={self.id}, name={self.name})"


class Book(Base):
    __tablename__ = "books"

    id: Mapped[UUID] = mapped_column(SA_UUID(as_uuid=True), primary_key=True)
    category_id: Mapped[UUID] = mapped_column(
        SA_UUID(as_uuid=True),
        ForeignKey("book_categories.id", ondelete="CASCADE"),
    )
    title: Mapped[str] = mapped_column(nullable=False, unique=True)
    author: Mapped[str] = mapped_column(nullable=False)

    notes: Mapped[list["BookNote"]] = relationship(
        back_populates="book",
    )

    def __repr__(self):
        return f"Book(id={self.id}, title={self.title}, author={self.author})"


class BookEpisode(Base):
    __tablename__ = "book_episodes"

    book_id: Mapped[UUID] = mapped_column(
        SA_UUID(as_uuid=True),
        ForeignKey("books.id", ondelete="CASCADE"),
        primary_key=True,
    )
    number: Mapped[int] = mapped_column(primary_key=True)
    hook: Mapped[str] = mapped_column(nullable=False)
    original_text: Mapped[str] = mapped_column(nullable=False)
    summary: Mapped[str] = mapped_column(nullable=False)
    cliffhanger: Mapped[str] = mapped_column(nullable=False)
    character: Mapped[str] = mapped_column(nullable=False)
    character_role: Mapped[str] = mapped_column(nullable=False)
    path: Mapped[str | None] = mapped_column(nullable=True)

    def __repr__(self) -> str:
        return (
            "BookEpisode("
            f"number={self.number},"
            f"path={self.path},"
            f"hook={self.hook})"
        )


class BookNote(Base):
    __tablename__ = "book_notes"

    book_id: Mapped[UUID] = mapped_column(
        SA_UUID(as_uuid=True),
        ForeignKey("books.id", ondelete="CASCADE"),
        primary_key=True,
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(nullable=False)
    text: Mapped[str] = mapped_column(nullable=False)

    book: Mapped["Book"] = relationship(
        back_populates="notes",
    )

    def __repr__(self) -> str:
        return f"BookNote(id={self.id}, title={self.title}, text={self.text})"
