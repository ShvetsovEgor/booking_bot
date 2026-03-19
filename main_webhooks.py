import os
import logging
import re
from datetime import datetime
from aiohttp import web
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, types, F, Router
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

# Загружаем переменные из .env (если файл есть рядом)
load_dotenv()

# --- НАСТРОЙКИ (Private Variables) ---
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME")
BASE_WEBHOOK_URL = os.getenv("BASE_WEBHOOK_URL")

WEBHOOK_PATH = "/webhook"
# Для Render/облака используем 0.0.0.0 и порт из переменной PORT
WEB_SERVER_HOST = "0.0.0.0"
WEB_SERVER_PORT = int(os.getenv("PORT", 8080))

# Твоя занятость (когда ты ЗАНЯТ)
BUSY_SCHEDULE = {
    0: [(16, 0, 17, 30)],
    1: [],
    2: [(9, 0, 15, 50)],
    3: [(9, 0, 10, 30), (14, 20, 20, 50)],
    4: [(12, 40, 15, 50)],
    5: [(10, 40, 12, 10), (14, 20, 15, 40)],
    6: []
}
VACANT_KEYWORDS = ["гид", "ведущий", "нужен"]

# --- ЛОГИКА ПРОВЕРКИ ---
def is_free(day_of_week, start_time_str, end_time_str=None):
    try:
        sh, sm = map(int, start_time_str.split(':'))
        slot_start = sh * 60 + sm

        if end_time_str:
            eh, em = map(int, end_time_str.split(':'))
            slot_end = eh * 60 + em
        else:
            slot_end = slot_start + 90

        for (bsh, bsm, beh, bem) in BUSY_SCHEDULE.get(day_of_week, []):
            busy_start = bsh * 60 + bsm
            busy_end = beh * 60 + bem

            overlap_start = max(slot_start, busy_start)
            overlap_end = min(slot_end, busy_end)

            if overlap_start < overlap_end:
                overlap_duration = overlap_end - overlap_start
                if overlap_duration > 10:
                    return False
                else:
                    logging.info(f"Допущен нахлест {overlap_duration} мин. на слоте {start_time_str}")

        return True
    except Exception as e:
        logging.error(f"Ошибка в расчете времени: {e}")
        return False

# --- ОБРАБОТЧИК ---
router = Router()

@router.message(F.chat.type.in_({"group", "supergroup"}), F.from_user.username == ADMIN_USERNAME)
async def auto_booking(message: types.Message):
    text = message.text or message.caption or ""
    lines = text.split('\n')
    booking_results = {}
    current_date, current_dow = None, None
    is_excursion_list = False

    for line in lines:
        clean = line.strip().lower()
        d_match = re.search(r'(\d{2})\.(\d{2})', line)
        if d_match:
            is_excursion_list = True
            current_date = d_match.group(0)
            day, month = map(int, d_match.groups())
            try:
                # 2026 год, как в твоем исходнике
                current_dow = datetime(2026, month, day).weekday()
                if current_date not in booking_results:
                    booking_results[current_date] = []
            except:
                current_dow = None
            continue

        if current_dow is not None and current_date:
            t_match = re.search(r'(\d{2}:\d{2})(?:[–-]\s?(\d{2}:\d{2}))?', line)
            if t_match:
                is_excursion_list = True
                is_vacant = any(word in clean for word in VACANT_KEYWORDS)
                if is_vacant:
                    start, end = t_match.group(1), t_match.group(2)
                    if is_free(current_dow, start, end):
                        booking_results[current_date].append(start)

    resp = [f"{d}: Я могу в {', '.join(s)}" for d, s in booking_results.items() if s]

    if resp:
        await message.reply("\n".join(resp))
    elif is_excursion_list:
        await message.reply("не могу")

# --- ЗАПУСК WEBHOOK ---
async def on_startup(bot: Bot):
    await bot.set_webhook(f"{BASE_WEBHOOK_URL}{WEBHOOK_PATH}")

def main():
    if not TOKEN:
        exit("Error: BOT_TOKEN variable not found.")

    bot = Bot(token=TOKEN)
    dp = Dispatcher()
    dp.include_router(router)
    dp.startup.register(on_startup)

    app = web.Application()
    webhook_requests_handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
    webhook_requests_handler.register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)

    logging.basicConfig(level=logging.INFO)
    web.run_app(app, host=WEB_SERVER_HOST, port=WEB_SERVER_PORT)

if __name__ == "__main__":
    main()