import logging

from datetime import UTC, datetime

from uuid6 import uuid7

from spytrend.auth.exceptions import AuthError
from spytrend.auth.id_provider import IdProvider
from spytrend.infra.db.transaction_manager import TransactionManager
from spytrend.users.exceptions import CreateUserError, UserAlreadyExistsError
from spytrend.users.gateways import UserGateway
from spytrend.users.models import User

logger = logging.getLogger(__name__)


class TelegramAuth:
    def __init__(
        self,
        id_provider: IdProvider,
        user_gateway: UserGateway,
        transaction_manager: TransactionManager,
    ):
        self.id_provider = id_provider
        self.user_gateway = user_gateway
        self.transaction_manager = transaction_manager

    async def auth(self):
        try:
            return await self.id_provider.get_current_user_id()
        except AuthError:
            pass
        user_id = uuid7()
        telegram_id = await self.id_provider.get_current_user_telegram_id()
        now = datetime.now(tz=UTC)
        new_user = User(
            id=user_id,
            telegram_id=telegram_id,
            created_at=now,
            updated_at=now,
        )
        try:
            await self.user_gateway.add(new_user)
            await self.transaction_manager.commit()
        except CreateUserError:
            logger.info(f"User not created: {new_user!r}")
            await self.transaction_manager.rollback()
            raise
        except UserAlreadyExistsError:
            logger.info(f"User already exists: {new_user!r}")
            await self.transaction_manager.rollback()
            raise
        return user_id
