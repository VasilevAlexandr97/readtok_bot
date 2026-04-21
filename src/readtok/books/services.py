import json
import logging
import math
import re

from dataclasses import dataclass
from pathlib import Path

from transliterate import translit
from uuid6 import uuid7

from readtok.books.episode_generator import Episode, EpisodeGenerator
from readtok.books.exceptions import BookCategoryNotFoundError
from readtok.books.fb2_book_parser import BookData, Fb2BookParser, SectionData
from readtok.books.gateways import (
    BookCategoryGateway,
    BookEpisodeGateway,
    BookGateway,
    BookNoteGateway,
)
from readtok.books.models import Book, BookEpisode, BookNote
from readtok.infra.db.transaction_manager import TransactionManager

logger = logging.getLogger(__name__)


@dataclass
class BookEpisodeRequest:
    number: int
    hook: str
    original_text: str
    summary: str
    cliffhanger: str
    character: str
    character_role: str
    path: str


@dataclass
class NoteRequest:
    id: int
    title: str
    text: str


@dataclass
class SaveBookRequest:
    title: str
    author: str
    category: str
    episodes: list[BookEpisodeRequest]
    notes: list[NoteRequest]


class BookService:
    def __init__(
        self,
        category_gateway: BookCategoryGateway,
        book_gateway: BookGateway,
        episode_gateway: BookEpisodeGateway,
        note_gateway: BookNoteGateway,
        transaction_manager: TransactionManager,
    ):
        self.category_gateway = category_gateway
        self.book_gateway = book_gateway
        self.episode_gateway = episode_gateway
        self.note_gateway = note_gateway
        self.transaction_manager = transaction_manager

    async def get_category_titles(self) -> list[str]:
        categories = await self.category_gateway.get_all()
        return [c.name for c in categories]

    async def is_book_exist(self, category: str) -> bool:
        return await self.book_gateway.is_exist(category)

    async def save_book(self, request: SaveBookRequest):
        category = await self.category_gateway.get_by_name(request.category)
        if category is None:
            raise BookCategoryNotFoundError(
                f"Book category {request.category} not found.",
            )
        book_id = uuid7()
        book = Book(
            id=book_id,
            title=request.title,
            author=request.author,
            category_id=category.id,
        )
        notes = [
            BookNote(
                id=note.id,
                book_id=book_id,
                title=note.title,
                text=note.text,
            )
            for note in request.notes
        ]
        episodes = [
            BookEpisode(
                book_id=book_id,
                number=episode.number,
                hook=episode.hook,
                original_text=episode.original_text,
                summary=episode.summary,
                cliffhanger=episode.cliffhanger,
                character=episode.character,
                character_role=episode.character_role,
            )
            for episode in request.episodes
        ]
        await self.book_gateway.add(book)
        await self.episode_gateway.bulk_insert(episodes)
        await self.note_gateway.bulk_insert(notes)

        logger.info(
            f"Book {request.title} saved with id {book_id}",
        )
        await self.transaction_manager.commit()


class BookImportService:
    def __init__(
        self,
        book_service: BookService,
        book_parser: Fb2BookParser,
        episode_generator: EpisodeGenerator,
    ):
        self.book_service = book_service
        self.book_parser = book_parser
        self.episode_generator = episode_generator
        self.cached_data: dict[Path, BookData] = {}

    def _load_book(self, file_path: Path) -> BookData:
        book_data = self.cached_data.get(file_path)
        if book_data is None:
            book_data = self.book_parser.parse(file_path)
            self.cached_data[file_path] = book_data
        return book_data

    def get_section_groups(
        self,
        file_path: Path,
        depth: int = 2,
    ) -> list[list[str]]:
        seen = set()
        result = []
        book_data = self._load_book(file_path)
        for section in book_data.sections:
            truncated = section.path[:depth]
            key = tuple(truncated)
            if key not in seen:
                seen.add(key)
                result.append(truncated)
        return result

    def get_sections_by_group(
        self,
        file_path: Path,
        group: list[str],
    ) -> list[SectionData]:
        book_data = self._load_book(file_path)
        return [s for s in book_data.sections if s.path[: len(group)] == group]

    def chunk_paragraphs(
        self,
        paragraphs: list[str],
        chunk_size: int = 5000,
    ) -> list[list[str]]:
        # TODO: решение в лоб, возможно стоит отрефакторить
        total_length_paragraphs = sum(len(p) for p in paragraphs)
        if total_length_paragraphs <= chunk_size:
            return [paragraphs]

        opt_chunks = math.ceil(total_length_paragraphs / chunk_size)
        opt_chunk_size = total_length_paragraphs / opt_chunks

        result = []
        current_chunk = []
        current_size = 0

        for paragraph in paragraphs:
            length_paragraph = len(paragraph)
            if current_size + length_paragraph <= opt_chunk_size:
                current_chunk.append(paragraph)
                current_size += length_paragraph
            else:
                result.append(current_chunk)
                current_chunk = [paragraph]
                current_size = length_paragraph

        if current_chunk:
            result.append(current_chunk)

        # Добавляем к каждому чанку, последний параграф предыдущего чанка
        # Чтобы каждый чанк был сбалансирован по длине
        original_chunks = [chunk[:] for chunk in result]
        for i in range(1, len(result)):
            result[i].insert(0, original_chunks[i - 1][-1])
        return result

    def book_folder_name(self, title: str) -> str:
        latin = translit(title, "ru", reversed=True)
        safe_name = re.sub(r"[^\w\s-]", "", latin).strip().lower()
        safe_name = re.sub(r"[\s_-]+", "_", safe_name).strip("_")
        return safe_name

    def _create_book_folder(self, book_title: str, output_dir: Path) -> Path:
        book_folder_name = self.book_folder_name(book_title)
        book_folder = output_dir / book_folder_name
        book_folder.mkdir(parents=True, exist_ok=True)
        return book_folder

    def save_chunk_episodes_to_json(
        self,
        section_path: list[str],
        chunk_number: int,
        chunk_text: str,
        chunk_episodes: list[Episode],
        output_dir: Path,
    ):
        chunk_file = output_dir / f"chunk_{chunk_number}.json"
        with chunk_file.open("w", encoding="utf-8") as f:
            data = {
                "section_path": section_path,
                "chunk_number": chunk_number,
                "chunk_text": chunk_text,
                "episodes": [
                    ep.model_dump(mode="python") for ep in chunk_episodes
                ],
            }
            json.dump(data, f, indent=4, ensure_ascii=False)

    async def import_book(
        self,
        file_path: Path,
        category: str,
        sections: list[SectionData],
        output_dir: Path,
    ):
        logger.info(f"Importing book: {file_path}")

        book_data = self._load_book(file_path)
        logger.info(f"Book notes: {book_data.notes}")
        if book_data.title is None:
            raise ValueError("Book title not found")
        if book_data.author is None:
            raise ValueError("Book author not found")

        if await self.book_service.is_book_exist(book_data.title):
            logger.info(f"Book {book_data.title} already exist")
            return

        book_folder = self._create_book_folder(book_data.title, output_dir)
        book_episodes = []
        start_episode_number = 1
        previes_episodes = []
        chunk_number = 1
        for section in sections:
            paragraph_chunks = self.chunk_paragraphs(section.paragraphs)
            for chunk in paragraph_chunks:
                chunk_text = "\n".join(chunk)
                result = await self.episode_generator.generate(
                    book_data.title,
                    book_data.author,
                    section.path,
                    chunk_text,
                    start_episode_number=start_episode_number,
                    previous_episodes=previes_episodes,
                )
                if result is None:
                    raise ValueError("Failed to generate episodes")
                book_episodes.extend(
                    BookEpisodeRequest(
                        number=ep.number,
                        hook=ep.hook,
                        original_text=ep.original_text,
                        summary=ep.summary,
                        cliffhanger=ep.cliffhanger,
                        character=ep.character,
                        character_role=ep.character_role,
                        path=";".join(section.path),
                    )
                    for ep in result.episodes
                )
                self.save_chunk_episodes_to_json(
                    section.path,
                    chunk_number,
                    chunk_text,
                    result.episodes,
                    book_folder,
                )
                chunk_number += 1
                previes_episodes = result.episodes[-2:]
                start_episode_number = result.episodes[-1].number + 1

        save_book_req = SaveBookRequest(
            title=book_data.title,
            author=book_data.author,
            category=category,
            episodes=book_episodes,
            notes=[
                NoteRequest(id=note.id, title=note.title, text=note.text)
                for note in book_data.notes
            ],
        )
        await self.book_service.save_book(save_book_req)
