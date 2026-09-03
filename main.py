import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand  # <--- Добавили импорт

from config import BOT_TOKEN

from handlers import (
    bell_router,
    privacy_router,
    schedule_router,
    start_router,
    teacher_router,
)


logging.basicConfig(
    level=logging.INFO,
    format=(
        "%(asctime)s | "
        "%(levelname)s | "
        "%(name)s | "
        "%(message)s"
    ),
)


# ---------------------------------------------------------------
# Регистрация команд в меню Telegram
# ---------------------------------------------------------------
async def setup_bot_commands(bot: Bot):
    commands = [
        BotCommand(command="start", description="Запустить бота / Помощь"),
        BotCommand(command="bell", description="Расписание звонков"),
        BotCommand(command="privacy", description="Политика конфиденциальности"),
    ]
    await bot.set_my_commands(commands)


async def run_bot():

    bot = Bot(
        token=BOT_TOKEN
    )

    dp = Dispatcher()

    # Устанавливаем меню команд в интерфейсе Telegram
    await setup_bot_commands(bot)

    # ---------------------------------------------------------------
    # Роутеры
    # ---------------------------------------------------------------

    # Команды
    dp.include_router(start_router)
    dp.include_router(bell_router)
    dp.include_router(privacy_router)

    # Классы
    dp.include_router(schedule_router)

    # Учителя
    dp.include_router(teacher_router)

    # ---------------------------------------------------------------
    # Предварительная загрузка расписания
    # ---------------------------------------------------------------

    try:

        from data_manager import (
            ensure_data_loaded,
        )

        logging.info(
            "Загружаю расписание перед запуском..."
        )

        success = await ensure_data_loaded()

        if success:

            logging.info(
                "Расписание успешно загружено."
            )

        else:

            logging.warning(
                "Не удалось загрузить расписание."
            )

    except Exception:

        logging.exception(
            "Ошибка предварительной загрузки расписания."
        )

    logging.info(
        "🚀 Бот запущен."
    )

    # ---------------------------------------------------------------
    # Polling
    # ---------------------------------------------------------------

    try:

        await dp.start_polling(
            bot
        )

    finally:

        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(
        run_bot()
    )
