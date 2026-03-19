import os
import re
import logging
import asyncio
import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from dotenv import load_dotenv
from telethon import TelegramClient, events
from telethon.sessions import StringSession

# Загружаем переменные
load_dotenv()

# --- КОНФИГУРАЦИЯ ---
API_ID = 37948236
API_HASH = '5ecb24535da6140dd138ad9a2dc226aa'
SESSION_STRING = os.getenv("TELEGRAM_SESSION")
TARGET_CHAT_ID = -1003885735770
ADMIN_USERNAME = "Egor_Shvetsov"
BUSY_SCHEDULE = {
    0: [(16, 0, 17, 30)], 1: [], 2: [(9, 0, 15, 50)],
    3: [(9, 0, 10, 30), (14, 20, 20, 50)], 4: [(12, 40, 15, 50)],
    5: [(10, 40, 12, 10), (14, 20, 15, 40)], 6: []
}
KEYWORDS = ["гид", "гида", "ведущий", "нужен", "нужна"]

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)


# --- ВЕБ-СЕРВЕР ДЛЯ RENDER (HEALTH CHECK) ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b"Bot is active and running!")


def run_health_check_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    logger.info(f"Мини-сервер запущен на порту {port}")
    server.serve_forever()


# --- ЛОГИКА ВРЕМЕНИ ---
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
            busy_start, busy_end = bsh * 60 + bsm, beh * 60 + bem
            overlap = min(slot_end, busy_end) - max(slot_start, busy_start)
            if overlap > 10: return False
        return True
    except:
        return False


# --- ОСНОВНАЯ ФУНКЦИЯ ---
async def main():
    # Инициализируем клиента СТРОГО внутри async main
    client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

    @client.on(events.NewMessage(chats=[TARGET_CHAT_ID]))
    async def handler(event):
        if event.out: return  # Игнорим себя

        sender = await event.get_sender()
        sender_name = getattr(sender, 'first_name', 'User')
        logger.info(f"Сообщение от {sender_name}...")

        lines = event.raw_text.split('\n')
        final_results = {}
        current_date, current_dow = None, None

        for line in lines:
            clean_line = line.lower()
            date_match = re.search(r'(\d{2})\.(\d{2})', line)
            if date_match:
                current_date = date_match.group(0)
                try:
                    d, m = int(date_match.group(1)), int(date_match.group(2))
                    current_dow = datetime(2026, m, d).weekday()
                    final_results[current_date] = []
                except:
                    current_date = None
                continue

            if current_date and current_dow is not None:
                time_match = re.search(r'(\d{2}:\d{2})(?:[–-]\s?(\d{2}:\d{2}))?', line)
                has_keyword = any(k in clean_line for k in KEYWORDS)
                if time_match and has_keyword:
                    start_t, end_t = time_match.group(1), time_match.group(2)
                    if is_free(current_dow, start_t, end_t):
                        final_results[current_date].append(start_t)

        response_lines = [f"{d}: Я могу в {', '.join(t)}" for d, t in final_results.items() if t]
        if response_lines:
            await event.reply("\n".join(response_lines))
            logger.info(f"Ответил на запрос.")

    logger.info("Подключение к Telegram...")
    await client.start()
    logger.info("Юзербот запущен и готов!")
    await client.run_until_disconnected()


if __name__ == "__main__":
    # 1. Запускаем мини-сервер в отдельном потоке
    threading.Thread(target=run_health_check_server, daemon=True).start()

    # 2. Запускаем основной цикл asyncio
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass