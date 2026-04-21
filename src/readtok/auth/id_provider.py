from abc import abstractmethod
from typing import Protocol
from uuid import UUID

from spytrend.auth.exceptions import AuthError
from spytrend.users.gateways import UserGateway


class IdProvider(Protocol):
    @abstractmethod
    async def get_current_user_id(self) -> UUID: ...

    @abstractmethod
    async def get_current_user_telegram_id(self) -> int: ...


class TelegramIdProvider(IdProvider):
    def __init__(self, telegram_id: int, gateway: UserGateway):
        self.telegram_id = telegram_id
        self.gateway = gateway

    async def get_current_user_telegram_id(self):
        return self.telegram_id

    async def get_current_user_id(self) -> UUID:
        user = await self.gateway.get_by_telegram_id(self.telegram_id)
        if user is None:
            raise AuthError(
                f"User with telegram_id: {self.telegram_id} not found",
            )
        return user.id


class WorkerIdProvider(IdProvider):
    async def get_current_user_telegram_id(self) -> int:
        return 0

    async def get_current_user_id(self) -> UUID:
        return UUID("00000000-0000-0000-0000-000000000000")
