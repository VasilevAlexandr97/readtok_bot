import logging

from sqlalchemy import ScalarResult, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from readtok.books.exceptions import (
    BookAlreadyExistsError,
    BookCategoryAlreadyExistsError,
    BookCategoryCreationError,
    BookCreationError,
)
from readtok.books.models import Book, BookCategory, BookNote, BookEpisode

logger = logging.getLogger(__name__)


class BookCategoryGateway:
    def __init__(self, session: AsyncSession):
        self.session = session

    # async def add(self, category: BookCategory):
    #     try:
    #         self.session.add(category)
    #         await self.session.flush()
    #     except IntegrityError as e:
    #         await self.session.rollback()
    #         if "unique constraint" in str(e.orig).lower():
    #             raise BookCategoryAlreadyExistsError
    #         logger.exception(
    #             f"Failed to add book category {category.name} "
    #             "to the database.",
    #         )
    #         raise BookCategoryCreationError

    async def bulk_insert(self, categories: list[BookCategory]):
        values = [
            {
                "id": category.id,
                "name": category.name,
            }
            for category in categories
        ]
        stmt = (
            insert(BookCategory)
            .values(values)
            .on_conflict_do_nothing(index_elements=["name"])
        )
        await self.session.execute(stmt)

    async def get_all(self) -> list[BookCategory]:
        stmt = select(BookCategory).order_by(BookCategory.name)
        return list(await self.session.scalars(stmt))

    async def get_by_name(self, name: str) -> BookCategory | None:
        stmt = select(BookCategory).where(BookCategory.name == name)
        return await self.session.scalar(stmt)


class BookGateway:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, book: Book):
        try:
            self.session.add(book)
            await self.session.flush()
        except IntegrityError as e:
            await self.session.rollback()
            if "unique constraint" in str(e.orig).lower():
                raise BookAlreadyExistsError
            logger.exception(
                f"Failed to add book category {book.title} to the database.",
            )
            raise BookCreationError

    async def is_exist(self, title: str) -> bool:
        stmt = select(Book).where(Book.title == title)
        result = await self.session.scalar(stmt)
        return result is not None


class BookEpisodeGateway:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def bulk_insert(self, book_episodes: list[BookEpisode]):
        values = [
            {
                "book_id": book_episode.book_id,
                "number": book_episode.number,
                "hook": book_episode.hook,
                "original_text": book_episode.original_text,
                "summary": book_episode.summary,
                "cliffhanger": book_episode.cliffhanger,
                "character": book_episode.character,
                "character_role": book_episode.character_role,
            }
            for book_episode in book_episodes
        ]
        stmt = insert(BookEpisode).values(values)
        await self.session.execute(stmt)


class BookNoteGateway:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def bulk_insert(self, book_notes: list[BookNote]):
        values = [
            {
                "id": book_note.id,
                "book_id": book_note.book_id,
                "title": book_note.title,
                "text": book_note.text,
            }
            for book_note in book_notes
        ]
        stmt = insert(BookNote).values(values)
        await self.session.execute(stmt)
