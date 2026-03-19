import os
import logging
import re
from datetime import datetime
from aiohttp import web
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, types, F, Router
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

# Загружаем настройки из .env или переменных окружения Render
load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME")
# BASE_WEBHOOK_URL = os.getenv("BASE_WEBHOOK_URL")
BASE_WEBHOOK_URL = "https://booking-bot-js5f.onrender.com"
WEBHOOK_PATH = "/webhook"
WEB_SERVER_HOST = "0.0.0.0"
WEB_SERVER_PORT = int(os.getenv("PORT", 8080))

# Твое актуальное расписание занятости (когда ты ЗАНЯТ)
BUSY_SCHEDULE = {
    0: [(16, 0, 17, 30)],  # Пн
    1: [],  # Вт
    2: [(9, 0, 15, 50)],  # Ср
    3: [(9, 0, 10, 30), (14, 20, 20, 50)],  # Чт
    4: [(12, 40, 15, 50)],  # Пт
    5: [(10, 40, 12, 10), (14, 20, 15, 40)],  # Сб
    6: []  # Вс
}
VACANT_KEYWORDS = ["гид", "ведущий", "нужен"]


# --- ЛОГИКА ---
def is_free(day_of_week, start_time_str, end_time_str=None):
    try:
        sh, sm = map(int, start_time_str.split(':'))
        slot_start = sh * 60 + sm
        slot_end = slot_start + 90 if not end_time_str else (lambda t: int(t[0]) * 60 + int(t[1]))(
            end_time_str.split(':'))

        for (bsh, bsm, beh, bem) in BUSY_SCHEDULE.get(day_of_week, []):
            busy_start, busy_end = bsh * 60 + bsm, beh * 60 + bem
            overlap = min(slot_end, busy_end) - max(slot_start, busy_start)

            if overlap > 10:  # Если нахлест больше 10 минут
                return False
        return True
    except:
        return False


router = Router()


@router.message(F.chat.type.in_({"group", "supergroup"}), F.from_user.username == ADMIN_USERNAME)
async def handle_admin_message(message: types.Message):
    text = message.text or message.caption or ""
    lines = text.split('\n')
    results = {}
    current_date, current_dow = None, None
    is_list = False

    for line in lines:
        clean = line.strip().lower()
        d_match = re.search(r'(\d{2})\.(\d{2})', line)
        if d_match:
            is_list = True
            current_date = d_match.group(0)
            try:
                current_dow = datetime(2026, int(d_match.group(2)), int(d_match.group(1))).weekday()
                results[current_date] = []
            except:
                current_dow = None
            continue

        if current_dow is not None and current_date:
            t_match = re.search(r'(\d{2}:\d{2})(?:[–-]\s?(\d{2}:\d{2}))?', line)
            if t_match:
                is_list = True
                if any(w in clean for w in VACANT_KEYWORDS):
                    start, end = t_match.group(1), t_match.group(2)
                    if is_free(current_dow, start, end):
                        results[current_date].append(start)

    resp = [f"{d}: Я могу в {', '.join(s)}" for d, s in results.items() if s]
    if resp:
        await message.reply("\n".join(resp))
    elif is_list:
        await message.reply("не могу")


# Эндпоинт для cron-job.org (чтобы Render не спал)
async def handle_ping(request):
    return web.Response(text="Bot is active")


async def on_startup(bot: Bot):
    await bot.set_webhook(f"{BASE_WEBHOOK_URL}{WEBHOOK_PATH}")


def main():
    bot = Bot(token=TOKEN)
    dp = Dispatcher()
    dp.include_router(router)
    dp.startup.register(on_startup)

    app = web.Application()
    app.router.add_get("/", handle_ping)  # Путь для пинга

    handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
    handler.register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)

    logging.basicConfig(level=logging.INFO)
    web.run_app(app, host=WEB_SERVER_HOST, port=WEB_SERVER_PORT)


if __name__ == "__main__":
    main()