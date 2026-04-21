import logging
import re
from uuid import UUID

from aiogram import Bot, F, Router, types
from aiogram.enums import ButtonStyle, ChatType
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandStart
from aiogram.utils.keyboard import InlineKeyboardBuilder
from dishka.integrations.aiogram import FromDishka, inject

from spytrend.auth.telegram_auth import TelegramAuth
from spytrend.channels.exceptions import UserChannelAlreadyExistsError
from spytrend.channels.models import UserChannel
from spytrend.channels.services import ChannelService

logger = logging.getLogger(__name__)

router = Router()
router.message.filter(F.chat.type == ChatType.PRIVATE)
router.callback_query.filter(F.message.chat.type == ChatType.PRIVATE)


@router.message(CommandStart())
@inject
async def start_handler(
    msg: types.Message,
    telegram_auth: FromDishka[TelegramAuth],
):
    await telegram_auth.auth()
    # builder = InlineKeyboardBuilder()
    # builder.row(
    #     types.InlineKeyboardButton
    # )
    await msg.answer(
        text=(
            "Привет, я отслеживаю каналы на вирусные посты.\n\n"
            "Пришли ссылку на канал или перешли пост из канала, "
            "чтобы я начал отслеживать его.\n\n"
            "Команды:\n"
            "/channels - список отслеживаемых каналов\n"
        ),
    )


channel_link_pattern = r"^https:\/\/t\.me\/([a-zA-Z0-9_]{2,32})$"


@router.message(
    F.text.regexp(pattern=channel_link_pattern).as_("channel_link"),
)
@inject
async def channel_link_handler(
    msg: types.Message,
    bot: FromDishka[Bot],
    channel_service: FromDishka[ChannelService],
    channel_link: re.Match[str],
):
    logger.debug(f"Channel link: {channel_link}, {type(channel_link)}")
    username = channel_link.group(1)
    logger.debug(f"Username: {username}")
    try:
        chat = await bot.get_chat(f"@{username}")
    except TelegramBadRequest:
        logger.debug(f"Channel not found: @{username}")
        await msg.answer(text="Канал не найден")
        return
    if chat.type != ChatType.CHANNEL:
        await msg.answer(text="Канал не найден")
        return
    logger.debug(f"Channel: {chat}")
    try:
        await channel_service.create(username=chat.username, title=chat.title)
    except UserChannelAlreadyExistsError:
        await msg.answer(text="Канал уже отслеживается")
        return
    await msg.answer(text="Ссылка сохранена")


def user_channels_kbd(user_channels: list[UserChannel]):
    kbd_builder = InlineKeyboardBuilder()
    for u_channel in user_channels:
        kbd_builder.row(
            types.InlineKeyboardButton(
                text=u_channel.channel.title,
                url=f"https://t.me/{u_channel.channel.tg_username}",
            ),
            types.InlineKeyboardButton(
                text="🗑️ Удалить",
                callback_data=f"delete_{u_channel.id}",
                style=ButtonStyle.DANGER,
            ),
        )
    return kbd_builder.as_markup()


@router.message(Command("channels"))
@inject
async def user_channels_handler(
    msg: types.Message,
    channel_service: FromDishka[ChannelService],
):
    user_channels = await channel_service.get_user_channels()
    if not user_channels:
        await msg.answer(
            text=(
                "Нет отслеживаемых каналов. "
                "Чтобы начать отслеживать канал, пришли ссылку на него."
            ),
        )
        return
    header_text = "Список отслеживаемых каналов:\n\n"
    channels_text = "\n".join(
        f"{i}. <a href='https://t.me/{u_channel.channel.tg_username}'>{u_channel.channel.title}</a>"
        for i, u_channel in enumerate(user_channels, start=1)
    )
    keyboard = user_channels_kbd(user_channels)
    await msg.answer(text=header_text + channels_text, reply_markup=keyboard)


@router.callback_query(F.data.startswith("delete_"))
@inject
async def delete_user_channel_handler(
    query: types.CallbackQuery,
    channel_service: FromDishka[ChannelService],
):
    user_channel_id = UUID(query.data.split("_")[1])
    logger.debug(f"User channel id: {user_channel_id}")
    await channel_service.delete_user_channel(user_channel_id)
    await query.answer(text="Канал удален")


@router.message()
async def echo_handler(msg: types.Message):
    await msg.answer(
        text="Пришли ссылку на канал в виде: https://t.me/channel_name",
    )
