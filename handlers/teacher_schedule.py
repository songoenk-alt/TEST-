from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram import F, Router, html
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from data_manager import (
    ensure_data_loaded,
    find_matching_teachers,
    get_teacher_schedule,
)

from .bell import get_lesson_status


router = Router()


KRASNOYARSK_TZ = ZoneInfo(
    "Asia/Krasnoyarsk"
)


DAYS_RU = [
    "понедельник",
    "вторник",
    "среда",
    "четверг",
    "пятница",
    "суббота",
    "воскресенье",
]


def _normalize_surname(
    value: str,
) -> str:
    return " ".join(
        value.strip().lower().split()
    )


def _looks_like_teacher_name(
    value: str,
) -> bool:
    text = value.strip()

    if not text:
        return False

    if text.startswith("/"):
        return False

    if text[0].isdigit():
        return False

    return any(
        char.isalpha()
        for char in text
    )


async def get_teacher_logic(
    surname: str,
    day_idx: int,
) -> str:

    day_name = DAYS_RU[
        day_idx % 7
    ]

    if day_name in {
        "суббота",
        "воскресенье",
    }:
        return (
            f"📅 <b>{day_name.capitalize()}</b>\n"
            "Уроков по расписанию нет."
        )

    teacher = await get_teacher_schedule(
        surname,
        day_name,
    )

    if teacher is None:
        return (
            f"📅 <b>{html.quote(day_name.capitalize())}</b>\n"
            "❌ Учитель не найден."
        )

    teacher_name = html.quote(
        str(teacher["name"])
    )

    lessons = teacher.get("lessons", {})

    lines = []
    if isinstance(lessons, dict):
        for num in range(1, 12):
            val = lessons.get(num, "")
            lines.append(f"{num}: {html.quote(str(val))}" if val else f"{num}:")
    elif isinstance(lessons, list):
        dict_lessons = {}
        for item in lessons:
            parts = str(item).split(":", 1)
            if len(parts) == 2 and parts[0].strip().isdigit():
                dict_lessons[int(parts[0].strip())] = parts[1].strip()
        for num in range(1, 12):
            val = dict_lessons.get(num, "")
            lines.append(f"{num}: {html.quote(str(val))}" if val else f"{num}:")

    content = "\n".join(lines)

    return (
        f"📅 <b>{html.quote(day_name.capitalize())}</b>\n"
        f"👨‍🏫 <b>{teacher_name}</b>\n"
        "--------------------------\n"
        f"<pre>{content}</pre>"
    )


async def send_teacher_schedule_response(
    target: Message | CallbackQuery,
    surname: str,
):

    now = datetime.now(
        KRASNOYARSK_TZ
    )

    day = now.weekday()

    if day < 4:
        first_day = day
        second_day = day + 1
    elif day == 4:
        first_day = 4
        second_day = 0
    else:
        first_day = 0
        second_day = 1

    status = await get_lesson_status()

    result1 = await get_teacher_logic(
        surname,
        first_day,
    )

    result2 = await get_teacher_logic(
        surname,
        second_day,
    )

    text_response = (
        "🔔 <b>Статус:</b>\n"
        f"{html.quote(status)}\n\n"
        + result1
        + "\n\n"
        + result2
    )

    if isinstance(target, Message):
        await target.answer(
            text_response,
            parse_mode="HTML",
        )
    else:
        await target.message.answer(
            text_response,
            parse_mode="HTML",
        )
        await target.answer()


@router.message(
    F.text
)
async def teacher_handler(
    message: Message,
):

    text = message.text.strip()

    if not _looks_like_teacher_name(text):
        return

    await ensure_data_loaded()

    matches = await find_matching_teachers(text)

    if not matches:
        await message.answer(
            f"❌ Учитель по запросу «<b>{html.quote(text)}</b>» не найден.",
            parse_mode="HTML",
        )
        return

    if len(matches) == 1:
        await send_teacher_schedule_response(
            message,
            matches[0],
        )
    else:
        buttons = []
        for teacher_fullname in matches:
            buttons.append(
                [
                    InlineKeyboardButton(
                        text=teacher_fullname,
                        callback_data=f"tch:{teacher_fullname[:50]}",
                    )
                ]
            )

        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

        await message.answer(
            f"🔍 Найдены варианты по запросу «<b>{html.quote(text)}</b>». Выберите нужного учителя:",
            reply_markup=keyboard,
            parse_mode="HTML",
        )


@router.callback_query(
    F.data.startswith("tch:")
)
async def teacher_callback_handler(
    callback: CallbackQuery,
):

    teacher_name = callback.data.split("tch:", 1)[1]

    await send_teacher_schedule_response(
        callback,
        teacher_name,
    )
