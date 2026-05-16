import asyncio
import json
import os
import sys
import logging
from datetime import datetime
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

# 1. Включаем логирование в stdout, чтобы Docker перехватывал все системные сообщения
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

logger.info("=== Скрипт bot.py запущен ===")

# Загружаем конфигурацию из .env
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID_RAW = os.getenv("ADMIN_ID", "0")
MONTHLY_LIMIT_GB = float(os.getenv("MONTHLY_LIMIT_GB", 1000.0))

logger.info(f"Загружен токен бота (длина): {len(BOT_TOKEN) if BOT_TOKEN else 0}")
logger.info(f"Загружен ADMIN_ID из .env: {ADMIN_ID_RAW}")

try:
    ADMIN_ID = int(ADMIN_ID_RAW)
except ValueError:
    logger.error(f"Ошибка: Не удалось перевести ADMIN_ID '{ADMIN_ID_RAW}' в число!")
    ADMIN_ID = 0

# Пути к файлам данных внутри контейнера
VNSTAT_JSON_PATH = "vnstat_data.json"
SYSTEM_JSON_PATH = "system_data.json"

if not BOT_TOKEN:
    logger.critical("КРИТИЧЕСКАЯ ОШИБКА: BOT_TOKEN не найден в переменной окружения!")
    sys.exit(1)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

def get_vnstat_data():
    """Читает трафик сетевых интерфейсов за текущий месяц в GiB."""
    try:
        if not os.path.exists(VNSTAT_JSON_PATH):
            logger.warning(f"Файл {VNSTAT_JSON_PATH} не найден")
            return None, 0, 0
            
        with open(VNSTAT_JSON_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        now = datetime.now()
        current_year = now.year
        current_month_num = now.month

        total_rx = 0
        total_tx = 0
        has_data = False

        for iface in data.get('interfaces', []):
            if iface['name'].startswith(('docker', 'veth', 'lo')):
                continue
            traffic = iface.get('traffic', {})
            months_list = traffic.get('month', []) or traffic.get('months', [])
            
            for m in months_list:
                date_info = m.get('date', {})
                if date_info.get('year') == current_year and date_info.get('month') == current_month_num:
                    total_rx += m.get('rx', 0)
                    total_tx += m.get('tx', 0)
                    has_data = True
                    break
        
        if not has_data:
            return None, 0, 0
            
        rx_gib = total_rx / 1024 / 1024 / 1024
        tx_gib = total_tx / 1024 / 1024 / 1024
        total_gib = rx_gib + tx_gib
        
        return total_gib, rx_gib, tx_gib
    except Exception as e:
        logger.error(f"Ошибка при чтении VNSTAT JSON: {e}")
        return None, 0, 0

def get_system_stats():
    """Читает сгенерированные хостом метрики CPU, RAM и Диска."""
    try:
        if not os.path.exists(SYSTEM_JSON_PATH):
            logger.warning(f"Файл {SYSTEM_JSON_PATH} не найден")
            return None
        with open(SYSTEM_JSON_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Ошибка при чтении SYSTEM JSON: {e}")
        return None

def get_keyboard():
    button = KeyboardButton(text="📊 Проверить статус")
    return ReplyKeyboardMarkup(keyboard=[[button]], resize_keyboard=True)

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    logger.info(f"Получена команда /start от пользователя {message.from_user.id}")
    if message.from_user.id == ADMIN_ID:
        await message.answer(
            f"Привет! Бот настроен на полный мониторинг сервера (Трафик + Нагрузка).\n"
            f"Лимит трафика: {MONTHLY_LIMIT_GB} GB.\n"
            f"Критический порог RAM: 50%.",
            reply_markup=get_keyboard(),
            parse_mode="Markdown"
        )

@dp.message(lambda message: message.text == "📊 Проверить статус")
async def send_stats(message: types.Message):
    logger.info(f"Пользователь {message.from_user.id} нажал на кнопку проверки статуса")
    
    if message.from_user.id != ADMIN_ID:
        logger.warning(f"Доступ заблокирован для пользователя {message.from_user.id} (Ожидался ADMIN_ID: {ADMIN_ID})")
        return

    total_tr, rx, tx = get_vnstat_data()
    sys_stats = get_system_stats()

    text = "🌐 *МОНИТОРИНГ СЕРВЕРА*\n\n"

    if total_tr is not None:
        text += (
            f"📈 *Сетевой трафик за месяц:*\n"
            f"📥 Принято (RX): `{rx:.2f} GB`\n"
            f"📤 Отправлено (TX): `{tx:.2f} GB`\n"
            f"🔄 *Итого расход:* `{total_tr:.2f} GB` / `{MONTHLY_LIMIT_GB} GB`\n"
        )
    else:
        text += "❌ Не удалось получить данные о трафике.\n"

    text += "\n"

    if sys_stats is not None:
        ram = sys_stats.get('ram', {})
        disk = sys_stats.get('disk', {})
        cpu = sys_stats.get('cpu', {})

        text += (
            f"🖥️ *Ресурсы системы:*\n"
            f"⚡ Загрузка CPU (LA 1m): `{cpu.get('load')}`\n"
            f"🧠 Оперативная память (RAM):\n"
            f"   `{ram.get('used_gb')} GB` / `{ram.get('total_gb')} GB` (*{ram.get('pct')}%*)\n"
            f"💾 Жесткий диск (Раздел /):\n"
            f"   Свободно `{disk.get('free_gb')} GB` из `{disk.get('total_gb')} GB`\n"
        )
    else:
        text += "❌ Не удалось получить данные ресурсов системы.\n"

    await message.answer(text, parse_mode="Markdown")

async def scheduled_tasks():
    alert_ram_sent = False
    while True:
        now = datetime.now()
        sys_stats = get_system_stats()
        if sys_stats:
            ram_pct = sys_stats.get('ram', {}).get('pct', 0)
            if ram_pct > 50.0:
                if not alert_ram_sent:
                    await bot.send_message(
                        ADMIN_ID,
                        f"🚨 *КРИТИЧЕСКИЙ АЛЕРТ.* Использование оперативной памяти RAM составило `{ram_pct}%` (Порог 50% превышен)!",
                        parse_mode="Markdown"
                    )
                    alert_ram_sent = True
            else:
                alert_ram_sent = False
        await asyncio.sleep(30)

async def main():
    logger.info("Запуск процесса Polling (опрос серверов Telegram)...")
    asyncio.create_task(scheduled_tasks())
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())