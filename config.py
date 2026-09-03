import os


BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

if not BOT_TOKEN:
    raise RuntimeError(
        "Не задан BOT_TOKEN. "
        "Добавь токен бота в переменную окружения BOT_TOKEN."
    )