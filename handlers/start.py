from aiogram import Router, types
from aiogram.filters import CommandStart


router = Router()


@router.message(CommandStart())
async def start_cmd(
    message: types.Message,
):
    await message.answer(
        "Привет! 👋\n\n"
        "Я помогу узнать расписание.\n\n"
        "👨‍🎓 <b>Для ученика</b>\n"
        "Введи свой класс, например:\n"
        "<code>9б</code>\n\n"
        "👨‍🏫 <b>Для учителя</b>\n"
        "Введи фамилию или её часть\n\n"
        "🔔 <b>Расписание звонков</b>\n"
        "Используй команду /bell\n\n"
        "📄 <b>Политика конфиденциальности</b>\n"
        "Используй команду /privacy",
        parse_mode="HTML",
    )
