from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram import F, Router, html
from aiogram.types import Message

from data_manager import (
    ensure_data_loaded,
    find_class_name,
    get_class_schedule,
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


def _normalize_class_input(
    value: str,
) -> str:
    """
    Нормализует ввод класса.

    Например:
        8а
        8А
        8 а
        8 А

    превращаются в:
        8а
    """

    return "".join(
        value.strip().lower().split()
    )


def _is_class_input(
    value: str,
) -> bool:
    """
    Проверяет формат класса.

    Допускаются:
        5а
        6б
        8в
        10а
        11у
    """

    text = _normalize_class_input(
        value
    )

    if not text:
        return False

    if not text[0].isdigit():
        return False

    if not any(
        char.isalpha()
        for char in text
    ):
        return False

    if not 2 <= len(text) <= 5:
        return False

    return True


async def get_schedule_logic(
    class_name: str,
    day_idx: int,
) -> str:

    day_name = DAYS_RU[
        day_idx % 7
    ]

    # В Excel нет субботы и воскресенья.
    if day_name in {
        "суббота",
        "воскресенье",
    }:

        return (
            f"📅 {day_name.capitalize()}\n"
            "Уроков по расписанию нет."
        )

    real_class_name = await find_class_name(
        class_name,
        day_name,
    )

    if real_class_name is None:

        return (
            f"📅 {html.quote(day_name.capitalize())}\n"
            f"❌ Класс "
            f"<b>{html.quote(class_name)}</b> "
            "не найден."
        )

    lessons = await get_class_schedule(
        real_class_name,
        day_name,
    )

    if lessons is None:

        return (
            f"📅 {html.quote(day_name.capitalize())}\n"
            "❌ Не удалось получить расписание."
        )

    if lessons:

        content = "\n".join(
            html.quote(
                str(lesson)
            )
            for lesson in lessons
        )

    else:

        content = "Уроков нет."

    return (
        f"📅 <b>{html.quote(day_name.capitalize())}</b>\n"
        f"🏫 Класс: "
        f"<b>{html.quote(real_class_name)}</b>\n"
        "--------------------------\n"
        f"<pre>{content}</pre>"
    )


async def _send_two_days(
    message: Message,
    class_name: str,
    first_day: int,
    second_day: int,
):

    status = await get_lesson_status()

    result1 = await get_schedule_logic(
        class_name,
        first_day,
    )

    result2 = await get_schedule_logic(
        class_name,
        second_day,
    )

    await message.answer(
        "🔔 <b>Статус:</b>\n"
        f"{html.quote(status)}\n\n"
        + result1
        + "\n\n"
        + result2,
        parse_mode="HTML",
    )


@router.message(
    F.text.regexp(
        r"^\s*\d{1,2}\s*[А-Яа-яA-Za-zЁё]\s*$"
    )
)
async def schedule_handler(
    message: Message,
):

    text = message.text.strip()

    class_name = _normalize_class_input(
        text
    )

    await ensure_data_loaded()

    now = datetime.now(
        KRASNOYARSK_TZ
    )

    day = now.weekday()

    # Понедельник - четверг:
    # сегодня + завтра.
    if day < 4:

        await _send_two_days(
            message,
            class_name,
            day,
            day + 1,
        )

        return

    # Пятница:
    # пятница + понедельник.
    if day == 4:

        await _send_two_days(
            message,
            class_name,
            4,
            0,
        )

        return

    # Суббота/воскресенье:
    # понедельник + вторник.
    await _send_two_days(
        message,
        class_name,
        0,
        1,
    )