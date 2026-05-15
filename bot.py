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
    Читает сгенерированный хостом JSON-файл, находит данные за текущий 
    календарный месяц по всем интерфейсам и возвращает (total, rx, tx) в GiB.
    """
    try:
        # Проверяем, существует ли файл
        if not os.path.exists(JSON_FILE_PATH):
            print(f"Ошибка: Файл {JSON_FILE_PATH} еще не создан планировщиком хоста.")
            return None, 0, 0
            
        # Читаем JSON-файл
        with open(JSON_FILE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        # Получаем текущие дату и время для точной фильтрации
        now = datetime.now()
        current_year = now.year
        current_month_num = now.month

        total_rx = 0
        total_tx = 0
        has_data = False

        # Проходим циклом по всем интерфейсам в системе
        for iface in data.get('interfaces', []):
            # Игнорируем локальные петли и подсети Docker
            if iface['name'].startswith(('docker', 'veth', 'lo')):
                continue
                
            traffic = iface.get('traffic', {})
            # Подстраховываемся на случай разных версий vnstat (month или months)
            months_list = traffic.get('month', []) or traffic.get('months', [])
            
            # Ищем нужный месяц за один линейный проход
            for m in months_list:
                date_info = m.get('date', {})
                
                # Проверяем строгое соответствие текущему году и месяцу
                if date_info.get('year') == current_year and date_info.get('month') == current_month_num:
                    total_rx += m.get('rx', 0)
                    total_tx += m.get('tx', 0)
                    has_data = True
                    break  # Нашли совпадение для интерфейса — выходим из внутреннего цикла
        
        if not has_data:
            return None, 0, 0
            
        # ИСПРАВЛЕНО: vnstat в json хранит данные в KiB. 
        # Переводим KiB в GiB делением на 1024 во второй степени.
        rx_gib = total_rx / (1000*3)
        tx_gib = total_tx / (1000*3)
        total_gib = rx_gib + tx_gib
        
        return total_gib, rx_gib, tx_gib

    except Exception as e:
        print(f"Ошибка при чтении JSON: {e}")
        traceback.print_exc()
        return None, 0, 0

def get_keyboard():
    """Создает кнопку для главного меню."""
    button = KeyboardButton(text="📊 Проверить трафик")
    return ReplyKeyboardMarkup(keyboard=[[button]], resize_keyboard=True)

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    """Обработка команды /start."""
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
    """Обработка нажатия на кнопку проверки трафика."""
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
    """Фоновые задачи: ежедневный отчет и проверка лимитов."""
    alert_sent_today = False 
    while True:
        now = datetime.now()
        
        # Утренний отчет в 8:00
        if now.hour == 8 and now.minute == 0:
            total, rx, tx = get_vnstat_data()
            if total is not None:
                msg = f"🔔 *Ежедневный отчет по серверу:*\nОбщий расход: `{total:.2f} GB` из `{MONTHLY_LIMIT_GB} GB`."
                await bot.send_message(ADMIN_ID, msg, parse_mode="Markdown")
            await asyncio.sleep(60)  # Защита от дублирования отправки в течение минуты
            
        # Проверка лимитов на превышение
        total, _, _ = get_vnstat_data()
        if total and total > MONTHLY_LIMIT_GB:
            if not alert_sent_today:
                await bot.send_message(
                    ADMIN_ID, 
                    f"🚨 *КРИТИЧЕСКИЙ АЛЕРТ!*\nОбщий трафик сервера превысил лимит! Использовано: `{total:.2f} GB`.",
                    parse_mode="Markdown"
                )
                alert_sent_today = True
        
        # Сброс флага алерта в полночь
        if now.hour == 0 and now.minute == 0:
            alert_sent_today = False

        await asyncio.sleep(30)

async def main():
    # Запускаем фоновый цикл задач и long polling бота
    asyncio.create_task(scheduled_tasks())
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())