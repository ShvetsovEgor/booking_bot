import os
import re
import logging
import asyncio
from datetime import datetime
from dotenv import load_dotenv
from telethon import TelegramClient, events
from telethon.sessions import StringSession


load_dotenv()


API_ID = 37948236
API_HASH = '5ecb24535da6140dd138ad9a2dc226aa'
SESSION_STRING = os.getenv("TELEGRAM_SESSION")

TARGET_CHAT_ID = os.getenv("TARGET_CHAT_ID")

# Твое расписание (когда ты ЗАНЯТ)
BUSY_SCHEDULE = {
    0: [(16, 0, 17, 30)],  # Пн
    1: [],  # Вт
    2: [(9, 0, 15, 50)],  # Ср
    3: [(9, 0, 10, 30), (14, 20, 20, 50)],  # Чт
    4: [(12, 40, 15, 50)],  # Пт
    5: [(10, 40, 12, 10), (14, 20, 15, 40)],  # Сб
    6: []  # Вс
}

KEYWORDS = ["гид", "гида", "ведущий", "нужен", "нужна"]

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


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


client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)


@client.on(events.NewMessage(chats=[TARGET_CHAT_ID]))
async def handler(event):
    if event.out:
        return
    sender = await event.get_sender()
    sender_name = getattr(sender, 'first_name', 'Кто-то')
    logger.info(f"Анализирую сообщение от {sender_name}...")

    text = event.raw_text
    lines = text.split('\n')

    final_results = {}
    current_date, current_dow = None, None

    for line in lines:
        clean_line = line.lower()

        # Ищем дату
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

        # Ищем время + ключевое слово
        if current_date and current_dow is not None:
            time_match = re.search(r'(\d{2}:\d{2})(?:[–-]\s?(\d{2}:\d{2}))?', line)
            has_keyword = any(k in clean_line for k in KEYWORDS)

            if time_match and has_keyword:
                start_t, end_t = time_match.group(1), time_match.group(2)
                if is_free(current_dow, start_t, end_t):
                    final_results[current_date].append(start_t)

    response_lines = [f"{d}: {', '.join(t)}" for d, t in final_results.items() if t]
    if response_lines:
        await event.reply("\n".join(response_lines))
        logger.info(f"Ответил пользователю {sender_name}")


async def main():
    logger.info("Бот-снайпер запущен. Слушаю ВСЕХ в целевом чате.")
    await client.start()
    await client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())