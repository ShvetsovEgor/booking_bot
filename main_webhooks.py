import logging
import re
from datetime import datetime
from aiohttp import web

from aiogram import Bot, Dispatcher, types, F, Router
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

# --- НАСТРОЙКИ ---
TOKEN = "8780241965:AAGSlbH24QrWPYyHWgFk3Oeqw3n519Z06As"
ADMIN_USERNAME = "Egor_Shvetsov"

# Твой домен или URL от ngrok (например: https://1234.ngrok-free.app)
BASE_WEBHOOK_URL = "https://ashlea-unmimetic-relaxingly.ngrok-free.dev"
WEBHOOK_PATH = "/webhook"
WEB_SERVER_HOST = "127.0.0.1"
WEB_SERVER_PORT = 8080

# Твоя занятость (когда ты ЗАНЯТ)
BUSY_SCHEDULE = {
    0: [(16, 00, 17, 30)],
    1: [],
    2: [(9, 0, 15, 50)],
    3: [(9, 0, 10, 30),
        (14, 20, 20, 50)],
    4: [(12, 40, 15, 50)],
    5: [(10, 40, 12, 10), (14, 20, 15, 40)],
    6: []
}
VACANT_KEYWORDS = ["гид", "ведущий", "нужен"]

# --- ЛОГИКА ПРОВЕРКИ ---
def is_free(day_of_week, start_time_str, end_time_str=None):
    """
    Проверяет, свободен ли слот с учетом 10-минутного допуска на нахлест.
    """
    try:
        # Переводим время слота в минуты
        sh, sm = map(int, start_time_str.split(':'))
        slot_start = sh * 60 + sm

        if end_time_str:
            eh, em = map(int, end_time_str.split(':'))
            slot_end = eh * 60 + em
        else:
            # Стандартная длительность 90 минут
            slot_end = slot_start + 90

        for (bsh, bsm, beh, bem) in BUSY_SCHEDULE.get(day_of_week, []):
            busy_start = bsh * 60 + bsm
            busy_end = beh * 60 + bem

            # Вычисляем границы пересечения
            overlap_start = max(slot_start, busy_start)
            overlap_end = min(slot_end, busy_end)

            # Если есть пересечение
            if overlap_start < overlap_end:
                overlap_duration = overlap_end - overlap_start

                # Если нахлест БОЛЬШЕ 10 минут — отклоняем
                if overlap_duration > 10:
                    return False
                else:
                    logging.info(f"Допущен нахлест в {overlap_duration} мин. на слоте {start_time_str}")

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

    # Флаг: было ли сообщение похоже на список экскурсий
    is_excursion_list = False

    for line in lines:
        clean = line.strip().lower()

        # 1. Ищем дату (например, 22.03)
        d_match = re.search(r'(\d{2})\.(\d{2})', line)
        if d_match:
            is_excursion_list = True  # Нашли дату — значит, это расписание
            current_date = d_match.group(0)
            day, month = map(int, d_match.groups())
            try:
                current_dow = datetime(2026, month, day).weekday()
                if current_date not in booking_results:
                    booking_results[current_date] = []
            except:
                current_dow = None
            continue

        # 2. Если внутри блока даты, ищем время
        if current_dow is not None and current_date:
            t_match = re.search(r'(\d{2}:\d{2})(?:[–-]\s?(\d{2}:\d{2}))?', line)
            if t_match:
                is_excursion_list = True  # Нашли время — тоже признак расписания

                # Проверяем, вакантно ли место (есть ли слово "гид" и т.д.)
                is_vacant = any(word in clean for word in VACANT_KEYWORDS)

                if is_vacant:
                    start, end = t_match.group(1), t_match.group(2)
                    if is_free(current_dow, start, end):
                        booking_results[current_date].append(start)

    # 3. Формируем ответ
    resp = [f"{d}: Я могу в {', '.join(s)}" for d, s in booking_results.items() if s]

    if resp:
        # Если нашли свободные слоты
        await message.reply("\n".join(resp))
    elif is_excursion_list:
        # Если это было расписание, но мы никуда не вписались
        await message.reply("не могу")
# --- ЗАПУСК WEBHOOK ---
async def on_startup(bot: Bot):
    await bot.set_webhook(f"{BASE_WEBHOOK_URL}{WEBHOOK_PATH}")

def main():
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