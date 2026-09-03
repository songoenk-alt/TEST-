from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram import Router, types
from aiogram.filters import Command

from data_manager import (
    ensure_data_loaded,
    get_bells,
)


router = Router()


KRASNOYARSK_TZ = ZoneInfo(
    "Asia/Krasnoyarsk"
)


def _to_minutes(value: str) -> int:
    """
    Преобразует HH:MM в количество минут.
    """

    hours, minutes = map(
        int,
        value.split(":"),
    )

    return hours * 60 + minutes


async def get_lesson_status() -> str:
    """
    Определяет текущий статус по расписанию звонков.
    """

    await ensure_data_loaded()

    bells = await get_bells()

    if not bells:
        return "🌙 Сейчас уроков нет."

    now = datetime.now(
        KRASNOYARSK_TZ
    )

    # Суббота/воскресенье.
    if now.weekday() >= 5:
        return "🌙 Сейчас выходной."

    current_minutes = (
        now.hour * 60
        + now.minute
    )

    for index, (
        number,
        start,
        end,
    ) in enumerate(bells):

        start_minutes = _to_minutes(
            start
        )

        end_minutes = _to_minutes(
            end
        )

        # Идёт урок.
        if (
            start_minutes
            <= current_minutes
            < end_minutes
        ):

            remaining = (
                end_minutes
                - current_minutes
            )

            return (
                f"🔔 Сейчас идёт "
                f"{number} урок\n"
                f"⏳ До конца: "
                f"{remaining} мин."
            )

        # Идёт перемена.
        if (
            index < len(bells) - 1
            and end_minutes
            <= current_minutes
            < _to_minutes(
                bells[index + 1][1]
            )
        ):

            remaining = (
                _to_minutes(
                    bells[index + 1][1]
                )
                - current_minutes
            )

            return (
                "☕️ Сейчас перемена\n"
                f"🔜 До {number + 1} урока: "
                f"{remaining} мин."
            )

    return "🌙 Сейчас уроков нет."


@router.message(Command("bell"))
async def cmd_bell(
    message: types.Message,
):

    await ensure_data_loaded()

    bells = await get_bells()
    status = await get_lesson_status()

    rows = []

    for number, start, end in bells:

        rows.append(
            f"{number}: {start} - {end}"
        )

    schedule_block = "\n".join(
        rows
    )

    response = (
        "🔔 <b>Статус:</b>\n"
        f"{status}\n\n"
        "🔔 <b>Расписание звонков:</b>\n"
        f"<pre>{schedule_block}</pre>"
    )

    await message.answer(
        response,
        parse_mode="HTML",
    )