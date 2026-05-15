import asyncio
import json
import os
import subprocess
from datetime import datetime
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

# Загружаем переменные из файла .env
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))
MONTHLY_LIMIT_GB = float(os.getenv("MONTHLY_LIMIT_GB", 1000.0))

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

def get_vnstat_data():
    """
    Вызывает vnstat для получения СУММАРНОЙ статистики по всему серверу.
    Возвращает (total, rx, tx) за текущий месяц в Гигабайтах.
    """
    try:
        # Вызываем vnstat с флагом --json без привязки к конкретному интерфейсу.
        # Это заставит vnstat выдать данные по всем интерфейсам.
        result = subprocess.check_output(['vnstat', '--json'], text=True)
        data = json.loads(result)
        
        total_rx = 0
        total_tx = 0
        
        # Проходим по всем найденным интерфейсам в системе
        for iface in data.get('interfaces', []):
            # Пропускаем docker и виртуальные интерфейсы, чтобы не задваивать локальный трафик
            if iface['name'].startswith(('docker', 'veth', 'lo')):
                continue
                
            months = iface.get('traffic', {}).get('month', [])
            if months:
                current_month = months[-1] # Данные за текущий месяц
                total_rx += current_month['rx']
                total_tx += current_month['tx']
        
        # Переводим суммарные KiB в GiB
        rx_gib = total_rx / (1024**2)
        tx_gib = total_tx / (1024**2)
        total_gib = rx_gib + tx_gib
        
        return total_gib, rx_gib, tx_gib
    except Exception as e:
        print(f"Ошибка при сборе общего трафика vnstat: {e}")
        return None, 0, 0

def get_keyboard():
    """Создает кнопку интерфейса."""
    button = KeyboardButton(text="📊 Проверить трафик")
    return ReplyKeyboardMarkup(keyboard=[[button]], resize_keyboard=True)

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        await message.answer(
            f"Привет! Бот настроен на сбор *ОБЩЕГО* трафика сервера.\n"
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
        await message.answer("Не удалось собрать суммарные данные vnstat.")

async def scheduled_tasks():
    alert_sent_today = False 
    while True:
        now = datetime.now()
        
        # Утренний отчет в 08:00
        if now.hour == 8 and now.minute == 0:
            total, rx, tx = get_vnstat_data()
            if total is not None:
                msg = f"🔔 *Ежедневный отчет по серверу:*\nОбщий расход: `{total:.2f} GB` из `{MONTHLY_LIMIT_GB} GB`."
                await bot.send_message(ADMIN_ID, msg, parse_mode="Markdown")
            await asyncio.sleep(60)
            
        # Проверка лимитов
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