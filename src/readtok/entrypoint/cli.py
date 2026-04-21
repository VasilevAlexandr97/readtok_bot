import asyncio
import logging
import sys

from dishka import AsyncContainer, make_async_container

from readtok.books.services import BookImportService
from readtok.cli.handlers import import_book, initdb
from readtok.entrypoint.config import Config, get_config
from readtok.entrypoint.di import (
    AIClientProvider,
    BooksProvider,
    BootstrapProvider,
    DBProvider,
)
from readtok.infra.bootstrap.seeder import DatabaseSeeder

logger = logging.getLogger(__name__)


async def main(container: AsyncContainer, cmd: str, args: list[str]):
    async with container() as req_c:
        if cmd == "initdb":
            database_seeder = await req_c.get(DatabaseSeeder)
            await initdb(database_seeder)
        if cmd == "importbook":
            book_import_service = await req_c.get(BookImportService)
            config = await req_c.get(Config)
            # TODO: прописать как понятные аргументы например --path и --output
            book_path = config.project_dir / args[0]
            output_dir = config.project_dir / args[1]
            await import_book(book_path, output_dir, book_import_service)


def run_cli():
    logging.basicConfig(level=logging.DEBUG)
    logger.info("Cli started")

    config = get_config()
    container = make_async_container(
        AIClientProvider(),
        DBProvider(),
        BootstrapProvider(),
        BooksProvider(),
        context={Config: config},
    )

    cmd = sys.argv[1]
    args = sys.argv[2:]
    logger.info(f"Command: {cmd} {args}")

    asyncio.run(main(container, cmd, args))


if __name__ == "__main__":
    run_cli()
