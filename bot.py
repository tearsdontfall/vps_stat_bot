import asyncio
import json
import os
import traceback
from datetime import datetime
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

# Загружаем конфигурацию из .env
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))
MONTHLY_LIMIT_GB = float(os.getenv("MONTHLY_LIMIT_GB", 1000.0))

# Путь к файлу с данными, который мы пробросим в контейнер
JSON_FILE_PATH = "vnstat_data.json"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

def get_vnstat_data():
    """
    Читает сгенерированный хостом JSON-файл и 
    возвращает (total, rx, tx) за текущий месяц в Гигабайтах.
    """
    try:
        # Проверяем, существует ли файл
        if not os.path.exists(JSON_FILE_PATH):
            print(f"Ошибка: Файл {JSON_FILE_PATH} еще не создан планировщиком хоста.")
            return None, 0, 0
            
        # Читаем JSON-файл
        with open(JSON_FILE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        total_rx = 0
        total_tx = 0
        has_data = False
        
        # Парсим интерфейсы (логика суммирования остается прежней)
        for iface in data.get('interfaces', []):
            if iface['name'].startswith(('docker', 'veth', 'lo')):
                continue
                
            traffic = iface.get('traffic', {})
            months = traffic.get('month', []) or traffic.get('months', [])
            
            if months:
                current_month = months[-1]  # Данные за текущий месяц
                total_rx += current_month.get('rx', 0)
                total_tx += current_month.get('tx', 0)
                has_data = True
        
        if not has_data:
            return None, 0, 0
            
        # Конвертируем из KiB/Bytes в GiB. 
        # Примечание: vnstat в json обычно отдает данные в Bytes или KiB.
        # Проверим единицы измерения. Если данные огромные, значит это Bytes.
        # Для стандартного vnstat json делитель для KiB -> GiB это 1024**2
        rx_gib = total_rx / (1024**2)
        tx_gib = total_tx / (1024**2)
        total_gib = rx_gib + tx_gib
        
        return total_gib, rx_gib, tx_gib

    except Exception as e:
        print(f"Ошибка при чтении JSON: {e}")
        traceback.print_exc()
        return None, 0, 0

def get_keyboard():
    button = KeyboardButton(text="📊 Проверить трафик")
    return ReplyKeyboardMarkup(keyboard=[[button]], resize_keyboard=True)

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        await message.answer(
            f"Привет! Бот настроен на чтение готовой статистики сервера.\n"
            f"Лимит: {MONTHLY_LIMIT_GB} GB.\n"
            f"Отчеты приходят каждый день в 8:00 МСК.",
            reply_markup=get_keyboard(),
            parse_mode="Markdown"
        )

@dp.message(lambda message: message.text == "📊 Проверить трафик")
async def send_stats(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return

    total, rx, tx = get_vnstat_data()
    if total is not None:
        text = (
            f"🌐 *Суммарный трафик сервера (Все интерфейсы):*\n\n"
            f"📥 Всего принято (RX): `{rx:.2f} GB`\n"
            f"📤 Всего отправлено (TX): `{tx:.2f} GB`\n"
            f"🔄 *Итого за месяц:* `{total:.2f} GB`\n"
        )
        if total > MONTHLY_LIMIT_GB:
            text += f"\n🚨 *ВНИМАНИЕ! Общий лимит превышен на {total - MONTHLY_LIMIT_GB:.2f} GB!*"
        
        await message.answer(text, parse_mode="Markdown")
    else:
        await message.answer("Не удалось прочитать данные трафика. На сервере идет обновление файла.")

async def scheduled_tasks():
    alert_sent_today = False 
    while True:
        now = datetime.now()
        if now.hour == 8 and now.minute == 0:
            total, rx, tx = get_vnstat_data()
            if total is not None:
                msg = f"🔔 *Ежедневный отчет по серверу:*\nОбщий расход: `{total:.2f} GB` из `{MONTHLY_LIMIT_GB} GB`."
                await bot.send_message(ADMIN_ID, msg, parse_mode="Markdown")
            await asyncio.sleep(60)
            
        total, _, _ = get_vnstat_data()
        if total and total > MONTHLY_LIMIT_GB:
            if not alert_sent_today:
                await bot.send_message(
                    ADMIN_ID, 
                    f"🚨 *КРИТИЧЕСКИЙ АЛЕРТ!*\nОбщий трафик сервера превысил лимит! Использовано: `{total:.2f} GB`.",
                    parse_mode="Markdown"
                )
                alert_sent_today = True
        
        if now.hour == 0 and now.minute == 0:
            alert_sent_today = False

        await asyncio.sleep(30)

async def main():
    asyncio.create_task(scheduled_tasks())
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
