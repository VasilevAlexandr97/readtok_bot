
from uuid6 import uuid7

from readtok.books.gateways import BookCategoryGateway
from readtok.books.models import BookCategory
from readtok.infra.db.transaction_manager import TransactionManager


class DatabaseSeeder:
    def __init__(
        self,
        book_category_gateway: BookCategoryGateway,
        transaction_manager: TransactionManager,
    ):
        self.book_category_gateway = book_category_gateway
        self.transaction_manager = transaction_manager

    async def seed_book_categories(self):
        category_names = [
            "Классика",
            "Детектив",
            "Приключения",
            "Ужасы",
            "Фантастика",
            "Фэнтези",
            "Романтика",
            "Драма",
        ]

        categories = [
            BookCategory(id=uuid7(), name=name) for name in category_names
        ]
        await self.book_category_gateway.bulk_insert(categories=categories)

    async def seed(self):
        await self.seed_book_categories()
        await self.transaction_manager.commit()
