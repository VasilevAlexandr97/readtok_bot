from collections.abc import AsyncIterable

# from aiogram.types import TelegramObject
from dishka import Provider, Scope, provide
from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from readtok.books.episode_generator import EpisodeGenerator
from readtok.books.fb2_book_parser import Fb2BookParser

# from readtok.auth.id_provider import (
#     IdProvider,
#     TelegramIdProvider,
# )
# from readtok.auth.telegram_auth import TelegramAuth
from readtok.books.gateways import (
    BookCategoryGateway,
    BookGateway,
    BookNoteGateway,
    BookEpisodeGateway,
)
from readtok.books.services import BookImportService, BookService
from readtok.entrypoint.config import Config
from readtok.infra.bootstrap.seeder import DatabaseSeeder
from readtok.infra.db.transaction_manager import TransactionManager

# from readtok.users.gateways import UserGateway


class DBProvider(Provider):
    @provide(scope=Scope.APP)
    def get_engine(self, config: Config) -> AsyncEngine:
        return create_async_engine(config.postgres.connection_url)

    @provide(scope=Scope.APP)
    def get_session_maker(
        self,
        engine: AsyncEngine,
    ) -> async_sessionmaker[AsyncSession]:
        return async_sessionmaker(
            engine,
            expire_on_commit=False,
            class_=AsyncSession,
            autoflush=False,
            autocommit=False,
        )

    @provide(scope=Scope.REQUEST)
    async def get_session(
        self,
        session_maker: async_sessionmaker[AsyncSession],
    ) -> AsyncIterable[AsyncSession]:
        async with session_maker() as session:
            yield session

    transaction_manager = provide(TransactionManager, scope=Scope.REQUEST)


class AIClientProvider(Provider):
    @provide(scope=Scope.APP)
    async def get_polza_client(
        self,
        config: Config,
    ) -> AsyncIterable[AsyncOpenAI]:
        polza_client = AsyncOpenAI(
            api_key=config.polza.api_key,
            base_url="https://polza.ai/api/v1",
        )
        yield polza_client
        await polza_client.close()


class BootstrapProvider(Provider):
    database_seeder = provide(DatabaseSeeder, scope=Scope.REQUEST)


# class UsersProvider(Provider):
#     user_gateway = provide(UserGateway, scope=Scope.REQUEST)


class BooksProvider(Provider):
    book_category_gateway = provide(BookCategoryGateway, scope=Scope.REQUEST)
    book_gateway = provide(BookGateway, scope=Scope.REQUEST)
    book_episode_gateway = provide(BookEpisodeGateway, scope=Scope.REQUEST)
    book_note_gateway = provide(BookNoteGateway, scope=Scope.REQUEST)
    book_service = provide(BookService, scope=Scope.REQUEST)
    book_import_service = provide(BookImportService, scope=Scope.REQUEST)
    fb2_book_parser = provide(Fb2BookParser, scope=Scope.REQUEST)

    @provide(scope=Scope.REQUEST)
    def get_episode_generator(self, client: AsyncOpenAI) -> EpisodeGenerator:
        return EpisodeGenerator(client=client, max_retries=3)


# class TgBotProvider(Provider):
#     @provide(scope=Scope.REQUEST, provides=IdProvider)
#     def get_id_provider(
#         self,
#         event: TelegramObject,
#         gateway: UserGateway,
#     ) -> TelegramIdProvider:
#         return TelegramIdProvider(
#             telegram_id=event.from_user.id,
#             gateway=gateway,
#         )

#     auth = provide(TelegramAuth, scope=Scope.REQUEST)
