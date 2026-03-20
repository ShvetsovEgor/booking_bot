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

load_dotenv()

# --- КОНФИГУРАЦИЯ ---
API_ID = 37948236
API_HASH = '5ecb24535da6140dd138ad9a2dc226aa'
SESSION_STRING = os.getenv("TELEGRAM_SESSION")
# ВАЖНО: Ник админа, которого слушаем
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME")
TARGET_CHAT_ID = os.getenv("TARGET_CHAT_ID")

# ADMIN_USERNAME = "traveltechinnopolis"
# TARGET_CHAT_ID = -1003885735770

# Твое расписание занятости
BUSY_SCHEDULE = {
    0: [(16, 0, 17, 30)], 1: [], 2: [(9, 0, 15, 50)],
    3: [(9, 0, 10, 30), (14, 20, 20, 50)], 4: [(12, 40, 15, 50)],
    5: [(10, 40, 12, 10), (14, 20, 15, 40)], 6: []
}

# Расширенный список ключевых слов для гибкости
KEYWORDS = ["гид", "гида", "ведущий", "нужен", "нужна", "экс", "взять"]

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)


# --- ВЕБ-СЕРВЕР ДЛЯ RENDER (HEALTH CHECK) ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b"Bot is active and flexible!")


def run_health_check_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
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


# --- ОСНОВНОЙ ОБРАБОТЧИК ---
async def main():
    client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

    # Запускаем клиент один раз
    await client.start()
    logger.info("Подключено! Проверяю доступ к чату...")

    try:
        entity = await client.get_entity(TARGET_CHAT_ID)
        logger.info(f"Чат найден: {entity.title}. Снайпер в засаде!")
    except Exception as e:
        logger.error(f"Не удалось найти чат по ID {TARGET_CHAT_ID}: {e}")
        return

    @client.on(events.NewMessage(chats=[TARGET_CHAT_ID]))
    async def handler(event):
        if event.out: return  # Не отвечаем сами себе

        sender = await event.get_sender()
        sender_username = getattr(sender, 'username', None)

        if sender_username != ADMIN_USERNAME:
            return

        text = event.raw_text
        lines = text.split('\n')
        final_results = {}
        current_date, current_dow = None, None

        for line in lines:
            clean_line = line.lower()

            # 1. Ищем дату (понимает 9.03 и 09.03)
            date_match = re.search(r'(\d{1,2})\.(\d{1,2})', line)
            if date_match:
                day, month = int(date_match.group(1)), int(date_match.group(2))
                current_date = f"{day:02d}.{month:02d}"
                try:
                    current_dow = datetime(2026, month, day).weekday()
                    if current_date not in final_results:
                        final_results[current_date] = []
                except:
                    current_date = None
                # НЕ используем continue, чтобы проверить эту же строку на наличие времени

            # 2. Ищем время и ключевое слово
            if current_date and current_dow is not None:
                # Паттерн для времени (понимает 6:30 и 06:30)
                time_match = re.search(r'(\d{1,2}:\d{2})(?:[–-]\s?(\d{1,2}:\d{2}))?', line)
                has_keyword = any(k in clean_line for k in KEYWORDS)

                if time_match and has_keyword:
                    start_t, end_t = time_match.group(1), time_match.group(2)
                    if is_free(current_dow, start_t, end_t):
                        # Добавляем только если такого времени для этой даты еще нет
                        if start_t not in final_results[current_date]:
                            final_results[current_date].append(start_t)

        # 3. Формируем и отправляем ответ
        response_lines = [f"{d} - {', '.join(t)}" for d, t in final_results.items() if t]
        if response_lines:
            await event.reply("\n".join(response_lines))
            logger.info(f"Ответ для @{sender_username} отправлен!")

    logger.info("Бот полностью запущен!")
    await client.run_until_disconnected()


if __name__ == "__main__":
    threading.Thread(target=run_health_check_server, daemon=True).start()
    asyncio.run(main())