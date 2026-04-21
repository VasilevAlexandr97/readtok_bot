import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage
from dishka import make_async_container
from dishka.integrations.aiogram import AiogramProvider, setup_dishka
from aiogram.types import LinkPreviewOptions
from spytrend.config import Config, get_config
from spytrend.di import (
    AnalyticsProvider,
    ChannelsProvider,
    DBProvider,
    ParsersProvider,
    PostsProvider,
    TgBotProvider,
    UsersProvider,
)
from spytrend.tgbot.handlers import router


async def main():
    logging.basicConfig(level=logging.DEBUG)
    config = get_config()
    default = DefaultBotProperties(
        parse_mode=ParseMode.HTML,
        link_preview=LinkPreviewOptions(is_disabled=True),
    )
    bot = Bot(token=config.telegram_bot.token, default=default)
    storage = RedisStorage.from_url(config.redis.connection_url)
    dp = Dispatcher(storage=storage)
    dp.include_router(router)

    container = make_async_container(
        DBProvider(),
        AnalyticsProvider(),
        ChannelsProvider(),
        PostsProvider(),
        ParsersProvider(),
        UsersProvider(),
        TgBotProvider(),
        AiogramProvider(),
        context={Config: config, Bot: bot},
    )

    setup_dishka(container=container, router=dp)
    try:
        await dp.start_polling(bot)
    finally:
        await container.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
