from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from spytrend.users.exceptions import CreateUserError, UserAlreadyExistsError
from spytrend.users.models import User


class UserGateway:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, new_user: User):
        try:
            self.session.add(new_user)
            await self.session.flush()
        except IntegrityError as exc:
            if "unique constraint" in str(exc.orig).lower():
                raise UserAlreadyExistsError
            raise CreateUserError

    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        stmt = select(User).where(User.telegram_id == telegram_id)
        return await self.session.scalar(stmt)
