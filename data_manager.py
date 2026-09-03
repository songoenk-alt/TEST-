import asyncio
import logging
import time
from datetime import time as dt_time
from io import BytesIO

import pandas as pd
import requests


logger = logging.getLogger(__name__)


SHEET_URL = (
    "https://docs.google.com/spreadsheets/d/"
    "1MO8-dP5RE2tX0_TFjYuN5gby-cRy29ESE3OmitblA7Q"
    "/export?format=xlsx"
)

CACHE_TIME = 9000  # 2 часа 30 минут


DAYS = (
    "понедельник",
    "вторник",
    "среда",
    "четверг",
    "пятница",
)


# -------------------------------------------------------------------
# Кэш
# -------------------------------------------------------------------

_cached_data: bytes | None = None
_last_update: float = 0.0

_schedule_cache: dict[
    str,
    dict[str, list[str]]
] = {}

_teacher_cache: dict[
    str,
    dict[str, dict[str, object]]
] = {}

_bells_cache: list[
    tuple[int, str, str]
] = []

_update_lock = asyncio.Lock()


# -------------------------------------------------------------------
# Вспомогательные функции
# -------------------------------------------------------------------

def normalize_text(value) -> str:
    if value is None:
        return ""

    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass

    return " ".join(
        str(value).strip().lower().split()
    )


def is_empty(value) -> bool:
    if value is None:
        return True

    try:
        if pd.isna(value):
            return True
    except (TypeError, ValueError):
        pass

    text = str(value).strip().lower()

    return text in {
        "",
        "nan",
        "nat",
        "none",
        "-",
    }


def clean_value(value) -> str:
    if is_empty(value):
        return ""

    return str(value).strip()


def _format_time(value) -> str:
    if is_empty(value):
        return ""

    if isinstance(value, dt_time):
        return value.strftime("%H:%M")

    if hasattr(value, "strftime"):
        try:
            return value.strftime("%H:%M")
        except (ValueError, TypeError):
            pass

    text = str(value).strip()

    if len(text) >= 5 and ":" in text:
        return text[:5]

    return text


# -------------------------------------------------------------------
# Скачивание Excel
# -------------------------------------------------------------------

def _download_excel() -> bytes | None:
    try:
        logger.info(
            "Загружаю расписание из Google Sheets..."
        )

        response = requests.get(
            SHEET_URL,
            timeout=15,
        )

        response.raise_for_status()

        if not response.content:
            raise ValueError(
                "Google Sheets вернул пустой файл."
            )

        with pd.ExcelFile(
            BytesIO(response.content)
        ) as excel:

            if not excel.sheet_names:
                raise ValueError(
                    "В полученном Excel нет листов."
                )

        logger.info(
            "Excel успешно загружен: %s байт.",
            len(response.content),
        )

        return response.content

    except Exception:
        logger.exception(
            "Ошибка при скачивании Excel."
        )

        return None


# -------------------------------------------------------------------
# Парсинг расписания классов
# -------------------------------------------------------------------

def _parse_class_schedules(
    excel_data: bytes,
) -> dict[str, dict[str, list[str]]]:
    result: dict[
        str,
        dict[str, list[str]]
    ] = {}

    try:
        with pd.ExcelFile(
            BytesIO(excel_data)
        ) as excel:

            available_sheets = {
                normalize_text(name): name
                for name in excel.sheet_names
            }

            for day in DAYS:

                if day not in available_sheets:
                    logger.warning(
                        "Не найден лист '%s'.",
                        day,
                    )
                    continue

                df = pd.read_excel(
                    excel,
                    sheet_name=available_sheets[day],
                    header=None,
                )

                if df.empty:
                    continue

                day_data: dict[
                    str,
                    list[str]
                ] = {}

                for col_idx in range(
                    df.shape[1]
                ):

                    header = normalize_text(
                        df.iloc[0, col_idx]
                    )

                    if not header:
                        continue

                    first_part = header.split()[0]

                    if not first_part:
                        continue

                    if not first_part[0].isdigit():
                        continue

                    if len(first_part) < 2:
                        continue

                    lessons: list[str] = []

                    for lesson_number in range(
                        1,
                        12,
                    ):

                        if lesson_number >= len(df):
                            break

                        value = clean_value(
                            df.iloc[
                                lesson_number,
                                col_idx,
                            ]
                        )

                        if value:
                            lessons.append(
                                f"{lesson_number}: {value}"
                            )

                    day_data[first_part] = lessons

                result[day] = day_data

        return result

    except Exception:
        logger.exception(
            "Ошибка при разборе расписания классов."
        )

        return {}


# -------------------------------------------------------------------
# Парсинг расписания учителей (все 11 уроков)
# -------------------------------------------------------------------

def _parse_teacher_schedules(
    excel_data: bytes,
) -> dict[
    str,
    dict[str, dict[str, object]]
]:
    result: dict[
        str,
        dict[str, dict[str, object]]
    ] = {}

    for day in DAYS:
        result[day] = {}

    try:
        with pd.ExcelFile(
            BytesIO(excel_data)
        ) as excel:

            available_sheets = {
                normalize_text(name): name
                for name in excel.sheet_names
            }

            for day in DAYS:

                sheet_name = f"п-{day}"

                if (
                    sheet_name
                    not in available_sheets
                ):
                    logger.warning(
                        "Не найден лист '%s'.",
                        sheet_name,
                    )
                    continue

                df = pd.read_excel(
                    excel,
                    sheet_name=available_sheets[
                        sheet_name
                    ],
                    header=None,
                )

                if df.empty:
                    continue

                lesson_columns: list[
                    tuple[int, int]
                ] = []

                for col_idx in range(
                    1,
                    df.shape[1],
                ):

                    header = df.iloc[
                        0,
                        col_idx,
                    ]

                    if is_empty(header):
                        continue

                    # Определяем номер урока из ячейки заголовка
                    lesson_number = None
                    if isinstance(header, (int, float)):
                        lesson_number = int(header)
                    elif hasattr(header, "day") and hasattr(header, "month"):
                        # Excel интерпретирует '6.01', '7.02' и т.д. как даты
                        lesson_number = header.day if header.day <= 11 else header.month
                    else:
                        try:
                            clean_header = str(header).strip().split(".")[0]
                            lesson_number = int(clean_header)
                        except (ValueError, TypeError):
                            pass

                    if lesson_number is None or not (1 <= lesson_number <= 11):
                        continue

                    lesson_columns.append(
                        (
                            col_idx,
                            lesson_number,
                        )
                    )

                lesson_columns.sort(key=lambda x: x[1])

                for row_idx in range(
                    1,
                    len(df),
                ):

                    teacher_name = clean_value(
                        df.iloc[
                            row_idx,
                            0,
                        ]
                    )

                    if not teacher_name:
                        continue

                    teacher_key = normalize_text(
                        teacher_name
                    )

                    lessons_dict: dict[int, str] = {i: "" for i in range(1, 12)}

                    for (
                        col_idx,
                        lesson_number,
                    ) in lesson_columns:

                        value = clean_value(
                            df.iloc[
                                row_idx,
                                col_idx,
                            ]
                        )

                        lessons_dict[lesson_number] = value

                    result[day][teacher_key] = {
                        "name": teacher_name,
                        "lessons": lessons_dict,
                    }

        return result

    except Exception:
        logger.exception(
            "Ошибка при разборе расписания учителей."
        )

        return result


# -------------------------------------------------------------------
# Парсинг звонков
# -------------------------------------------------------------------

def _parse_bells(
    excel_data: bytes,
) -> list[tuple[int, str, str]]:
    try:
        df = pd.read_excel(
            BytesIO(excel_data),
            sheet_name="звонки",
            header=0,
        )

        bells: list[
            tuple[int, str, str]
        ] = []

        for _, row in df.iterrows():

            if len(row) < 3:
                continue

            try:
                number = int(
                    row.iloc[0]
                )
            except (
                ValueError,
                TypeError,
            ):
                continue

            start = _format_time(
                row.iloc[1]
            )

            end = _format_time(
                row.iloc[2]
            )

            if not start or not end:
                continue

            bells.append(
                (
                    number,
                    start,
                    end,
                )
            )

        if bells:
            return bells

    except Exception:
        logger.exception(
            "Ошибка при чтении листа 'звонки'."
        )

    return [
        (1, "08:00", "08:40"),
        (2, "08:50", "09:30"),
        (3, "09:50", "10:30"),
        (4, "10:50", "11:30"),
        (5, "11:50", "12:30"),
        (6, "12:40", "13:20"),
        (7, "13:40", "14:20"),
        (8, "14:40", "15:20"),
        (9, "15:40", "16:20"),
        (10, "16:30", "17:10"),
        (11, "17:20", "18:00"),
    ]


# -------------------------------------------------------------------
# Обновление кэша
# -------------------------------------------------------------------

async def _update_cache() -> bool:
    global _cached_data
    global _last_update
    global _schedule_cache
    global _teacher_cache
    global _bells_cache

    async with _update_lock:

        now = time.monotonic()

        if (
            _cached_data is not None
            and now - _last_update < CACHE_TIME
        ):
            return True

        data = await asyncio.to_thread(
            _download_excel
        )

        if data is None:
            return _cached_data is not None

        schedules = await asyncio.to_thread(
            _parse_class_schedules,
            data,
        )

        teachers = await asyncio.to_thread(
            _parse_teacher_schedules,
            data,
        )

        bells = await asyncio.to_thread(
            _parse_bells,
            data,
        )

        _cached_data = data
        _schedule_cache = schedules
        _teacher_cache = teachers
        _bells_cache = bells
        _last_update = time.monotonic()

        logger.info(
            "Кэш расписания успешно обновлён."
        )

        return True


async def ensure_data_loaded() -> bool:
    now = time.monotonic()

    if (
        _cached_data is None
        or now - _last_update >= CACHE_TIME
    ):
        return await _update_cache()

    return True


# -------------------------------------------------------------------
# Классы
# -------------------------------------------------------------------

async def find_class_name(
    class_name: str,
    day_name: str,
) -> str | None:
    await ensure_data_loaded()

    day_key = normalize_text(day_name)
    class_key = normalize_text(class_name)

    day_data = _schedule_cache.get(
        day_key,
        {},
    )

    if class_key in day_data:
        return class_key

    for name in day_data:

        if normalize_text(
            name
        ) == class_key:
            return name

    return None


async def get_class_schedule(
    class_name: str,
    day_name: str,
) -> list[str] | None:
    await ensure_data_loaded()

    day_key = normalize_text(day_name)
    class_key = normalize_text(class_name)

    day_data = _schedule_cache.get(
        day_key,
        {},
    )

    if class_key in day_data:
        return day_data[class_key]

    for name, lessons in day_data.items():

        if normalize_text(
            name
        ) == class_key:
            return lessons

    return None


# -------------------------------------------------------------------
# Учителя
# -------------------------------------------------------------------

async def find_matching_teachers(query: str) -> list[str]:
    await ensure_data_loaded()

    query_norm = normalize_text(query)
    if not query_norm:
        return []

    found_names: set[str] = set()

    for day_data in _teacher_cache.values():
        for teacher in day_data.values():
            full_name = str(teacher["name"]).strip()
            name_norm = normalize_text(full_name)
            first_word = name_norm.split()[0] if name_norm else ""

            if first_word.startswith(query_norm) or query_norm in name_norm:
                found_names.add(full_name)

    return sorted(list(found_names))


async def get_teacher_schedule(
    surname: str,
    day_name: str,
) -> dict[str, object] | None:
    await ensure_data_loaded()

    day_key = normalize_text(day_name)
    surname_key = normalize_text(surname)

    day_data = _teacher_cache.get(
        day_key,
        {},
    )

    if not surname_key:
        return None

    for data in day_data.values():
        teacher_name = str(data["name"]).strip()
        if normalize_text(teacher_name) == surname_key:
            return data

    exact_matches = []
    for data in day_data.values():
        teacher_name = normalize_text(str(data["name"]))
        first_word = teacher_name.split()[0] if teacher_name else ""
        if first_word == surname_key:
            exact_matches.append(data)

    if len(exact_matches) == 1:
        return exact_matches[0]

    partial_matches = []
    for data in day_data.values():
        teacher_name = normalize_text(str(data["name"]))
        first_word = teacher_name.split()[0] if teacher_name else ""
        if first_word.startswith(surname_key) or surname_key in teacher_name:
            partial_matches.append(data)

    if len(partial_matches) == 1:
        return partial_matches[0]

    return None


# -------------------------------------------------------------------
# Звонки
# -------------------------------------------------------------------

async def get_bells() -> list[
    tuple[int, str, str]
]:
    await ensure_data_loaded()

    return list(_bells_cache)