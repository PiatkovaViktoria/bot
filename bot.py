import asyncio
import logging
import os

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from dotenv import load_dotenv


# =========================
# НАСТРОЙКИ
# =========================

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
MODERATOR_ID = int(os.getenv("MODERATOR_ID"))
CHANNEL_ID = os.getenv("CHANNEL_ID")

if not BOT_TOKEN:
    raise ValueError("Не указан BOT_TOKEN в .env")

if not CHANNEL_ID:
    raise ValueError("Не указан CHANNEL_ID в .env")


# =========================
# BOT / DISPATCHER
# =========================

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(
        parse_mode=ParseMode.HTML
    )
)

dp = Dispatcher()


# =========================
# СОСТОЯНИЯ
# =========================

class StoryState(StatesGroup):
    waiting_for_story = State()


# =========================
# КЛАВИАТУРА ДЛЯ ПОЛЬЗОВАТЕЛЯ
# =========================

def start_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📖 Прислать свою историю",
                    callback_data="send_story"
                )
            ]
        ]
    )


# =========================
# КЛАВИАТУРА МОДЕРАЦИИ
# =========================

def moderation_keyboard(user_id: int):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Принять",
                    callback_data=f"approve:{user_id}"
                ),
                InlineKeyboardButton(
                    text="❌ Отклонить",
                    callback_data=f"reject:{user_id}"
                )
            ]
        ]
    )


# =========================
# /START
# =========================

@dp.message(CommandStart())
async def start_handler(message: Message):

    text = (
        "👋 <b>Привет!</b>\n\n"
        "Здесь ты можешь прислать свою историю, "
        "которую после модерации мы опубликуем в канале.\n\n"
        "Нажми кнопку ниже, чтобы отправить историю 👇"
    )

    await message.answer(
        text,
        reply_markup=start_keyboard()
    )


# =========================
# КНОПКА "ПРИСЛАТЬ ИСТОРИЮ"
# =========================

@dp.callback_query(F.data == "send_story")
async def send_story_handler(
    callback: CallbackQuery,
    state: FSMContext
):

    await state.set_state(
        StoryState.waiting_for_story
    )

    await callback.message.answer(
        "✍️ <b>Напишите свою историю и отправьте её "
        "одним сообщением.</b>\n\n"
        "После этого она будет отправлена на модерацию.\n\n"
        "Минимум: 20 символов\n"
        "Максимум: 5000 символов."
    )

    await callback.answer()


# =========================
# ПОЛУЧЕНИЕ ИСТОРИИ
# =========================

@dp.message(StoryState.waiting_for_story)
async def receive_story(
    message: Message,
    state: FSMContext
):

    # Принимаем только текст
    if not message.text:

        await message.answer(
            "⚠️ Пожалуйста, отправьте историю "
            "именно текстовым сообщением."
        )

        return

    story = message.text.strip()

    # Проверяем длину
    if len(story) < 20:

        await message.answer(
            "⚠️ История слишком короткая.\n"
            "Напишите минимум 20 символов."
        )

        return

    if len(story) > 5000:

        await message.answer(
            "⚠️ История слишком длинная.\n"
            "Максимальная длина — 5000 символов."
        )

        return

    user = message.from_user

    # =========================
    # СООБЩЕНИЕ ПОЛЬЗОВАТЕЛЮ
    # =========================

    await message.answer(
        "✅ <b>История отправлена на модерацию!</b>\n\n"
        "Если она успешно пройдёт проверку, "
        "ваша история будет опубликована в канале."
    )

    # =========================
    # ИНФОРМАЦИЯ ОБ АВТОРЕ
    # =========================

    username = (
        f"@{user.username}"
        if user.username
        else "нет username"
    )

    # =========================
    # СООБЩЕНИЕ МОДЕРАТОРУ
    # =========================

    moderator_text = (
        "📩 <b>НОВАЯ ИСТОРИЯ</b>\n\n"

        f"<b>Автор:</b> {user.full_name}\n"
        f"<b>Username:</b> {username}\n"
        f"<b>ID:</b> <code>{user.id}</code>\n\n"

        "━━━━━━━━━━━━━━\n\n"

        f"{story}\n\n"

        "━━━━━━━━━━━━━━"
    )

    await bot.send_message(
        chat_id=MODERATOR_ID,
        text=moderator_text,
        reply_markup=moderation_keyboard(user.id)
    )

    # Очищаем состояние
    await state.clear()


# =========================
# ПРИНЯТЬ ИСТОРИЮ
# =========================

@dp.callback_query(F.data.startswith("approve:"))
async def approve_story(callback: CallbackQuery):

    # Проверяем, что кнопку нажал именно модератор
    if callback.from_user.id != MODERATOR_ID:

        await callback.answer(
            "Нет доступа.",
            show_alert=True
        )

        return

    # Получаем ID пользователя
    user_id = int(
        callback.data.split(":")[1]
    )

    # Получаем текст сообщения модератора
    moderation_message = callback.message.text

    # Разделитель
    separator = "━━━━━━━━━━━━━━"

    try:

        story = moderation_message.split(
            separator
        )[1].strip()

    except (IndexError, AttributeError):

        await callback.answer(
            "Ошибка: не удалось получить историю.",
            show_alert=True
        )

        return

    # =========================
    # ПУБЛИКАЦИЯ В КАНАЛ
    # =========================

    channel_text = story

    try:

        await bot.send_message(
            chat_id=CHANNEL_ID,
            text=channel_text
        )

    except Exception as e:

        logging.error(
            f"Ошибка публикации: {e}"
        )

        await callback.answer(
            "❌ Не удалось опубликовать историю.",
            show_alert=True
        )

        return

    # =========================
    # УБИРАЕМ КНОПКИ У МОДЕРАТОРА
    # =========================

    await callback.message.edit_reply_markup(
        reply_markup=None
    )

    await callback.message.answer(
        "✅ История опубликована в канале."
    )

    # =========================
    # СООБЩЕНИЕ АВТОРУ
    # =========================

    try:

        await bot.send_message(
            chat_id=user_id,

            text=(
                "🎉 <b>Ваша история прошла модерацию!</b>\n\n"
                "Она опубликована в нашем канале ❤️\n\n"
                "Хотите отправить ещё одну?"
            ),

            reply_markup=start_keyboard()
        )

    except Exception as e:

        logging.warning(
            f"Не удалось уведомить автора {user_id}: {e}"
        )

    await callback.answer(
        "История опубликована!"
    )


# =========================
# ОТКЛОНИТЬ ИСТОРИЮ
# =========================

@dp.callback_query(F.data.startswith("reject:"))
async def reject_story(callback: CallbackQuery):

    # Проверяем, что кнопку нажал именно модератор
    if callback.from_user.id != MODERATOR_ID:

        await callback.answer(
            "Нет доступа.",
            show_alert=True
        )

        return

    # Получаем ID пользователя
    user_id = int(
        callback.data.split(":")[1]
    )

    # Убираем кнопки у модератора
    await callback.message.edit_reply_markup(
        reply_markup=None
    )

    # Сообщение модератору
    await callback.message.answer(
        "❌ История отклонена."
    )

    # =========================
    # СООБЩЕНИЕ АВТОРУ
    # =========================

    try:

        await bot.send_message(
            chat_id=user_id,

            text=(
                "❌ <b>К сожалению, ваша история "
                "не прошла модерацию.</b>\n\n"
                "Она не будет опубликована в канале.\n\n"
                "Вы можете отправить другую историю:"
            ),

            reply_markup=start_keyboard()
        )

    except Exception as e:

        logging.warning(
            f"Не удалось уведомить автора {user_id}: {e}"
        )

    await callback.answer(
        "История отклонена."
    )


# =========================
# ЗАПУСК
# =========================

async def main():

    logging.basicConfig(
        level=logging.INFO
    )

    print("Бот запущен!")

    await dp.start_polling(bot)


# =========================
# MAIN
# =========================

if __name__ == "__main__":

    asyncio.run(main())