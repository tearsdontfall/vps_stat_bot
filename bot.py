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

# Настройка логирования в стандартный вывод (stdout) для Docker логов
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

try:
    ADMIN_ID = int(ADMIN_ID_RAW)
except ValueError:
    logger.error(f"Ошибка: Не удалось перевести ADMIN_ID '{ADMIN_ID_RAW}' в число!")
    ADMIN_ID = 0

VNSTAT_JSON_PATH = "vnstat_data.json"
SYSTEM_JSON_PATH = "system_data.json"

if not BOT_TOKEN:
    logger.critical("КРИТИЧЕСКАЯ ОШИБКА: BOT_TOKEN не найден в переменной окружения!")
    sys.exit(1)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

def get_vnstat_data():
    """Читает трафик сетевых интерфейсов за текущий месяц из vnstat_data.json."""
    try:
        if not os.path.exists(VNSTAT_JSON_PATH):
            logger.warning(f"Файл {VNSTAT_JSON_PATH} не найден")
            return None, 0, 0
        with open(VNSTAT_JSON_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        now = datetime.now()
        current_year = now.year
        current_month_num = now.month
        total_rx, total_tx = 0, 0
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
        return rx_gib + tx_gib, rx_gib, tx_gib
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
    """Формирует кнопку для интерфейса Telegram."""
    button = KeyboardButton(text="📊 Проверить статус")
    return ReplyKeyboardMarkup(keyboard=[[button]], resize_keyboard=True)

@dp.message()
async def handle_all_messages(message: types.Message):
    """Единый диспетчер сообщений с проверкой прав администратора."""
    logger.info(f"📢 Входящий запрос: '{message.text}' от ID: {message.from_user.id}")
    
    if message.from_user.id != ADMIN_ID:
        logger.warning(f"🔒 Доступ заблокирован для ID {message.from_user.id}. Ожидался ADMIN_ID: {ADMIN_ID}")
        await message.answer("❌ У вас нет доступа к управлению этим сервером.")
        return

    if message.text == "/start":
        await message.answer(
            f"Привет! Бот успешно обновлен и готов к мониторингу сервера.\n"
            f"Лимит трафика: `{MONTHLY_LIMIT_GB} GB`.\n\n"
            f"Используй кнопку ниже для проверки ресурсов.",
            reply_markup=get_keyboard(),
            parse_mode="Markdown"
        )
        return

    if message.text in ["📊 Проверить статус", "Проверить трафик"]:
        logger.info(f"🔄 Обработка запроса статистики для администратора...")
        
        total_tr, rx, tx = get_vnstat_data()
        sys_stats = get_system_stats()
        
        text = "🌐 *МОНИТОРИНГ СЕРВЕРА*\n\n"
        
        if total_tr is not None:
            text += (
                f"📈 *Сетевой трафик за месяц:*\n"
                f"📥 RX: `{rx:.2f} GB`\n"
                f"📤 TX: `{tx:.2f} GB`\n"
                f"🔄 Всего расход: `{total_tr:.2f} GB` / `{MONTHLY_LIMIT_GB} GB`\n"
            )
        else:
            text += "❌ Данные о трафике vnStat еще не сгенерированы.\n"
            
        if sys_stats is not None:
            ram = sys_stats.get('ram', {})
            disk = sys_stats.get('disk', {})
            cpu = sys_stats.get('cpu', {})
            text += (
                f"\n🖥️ *Ресурсы:*\n"
                f"⚡ CPU LA (1m): `{cpu.get('load', '0')}`\n"
                f"🧠 RAM: `{ram.get('used_gb', '0')} GB` / `{ram.get('total_gb', '0')} GB` (*{ram.get('pct', '0')}%*)\n"
                f"💾 Диск: свободно `{disk.get('free_gb', '0')} GB` из `{disk.get('total_gb', '0')} GB`"
            )
        else:
            text += "\n❌ Системные метрики (system_data.json) пустые или еще не обновлены скриптом."

        await message.answer(text, reply_markup=get_keyboard(), parse_mode="Markdown")
        return

async def scheduled_tasks():
    """Фоновый цикл проверки нагрузки RAM с максимальной защитой от ошибок типов."""
    while True:
        sys_stats = get_system_stats()
        if sys_stats:
            try:
                # Получаем значение, убираем пробелы и знаки процентов
                ram_pct_raw = str(sys_stats.get('ram', {}).get('pct', '0')).replace('%', '').strip()
                
                # Проверяем, что строка не пустая и содержит число
                if ram_pct_raw and ram_pct_raw != "None":
                    ram_pct = float(ram_pct_raw)
                    
                    # Если память заполнена более чем на 50%, отправляем алерт
                    if ram_pct > 50.0:
                        await bot.send_message(
                            ADMIN_ID, 
                            f"🚨 *КРИТИЧЕСКИЙ АЛЕРТ:* Использование оперативной памяти составляет `{ram_pct}%`!",
                            parse_mode="Markdown"
                        )
            except (ValueError, TypeError) as e:
                logger.error(f"Ошибка конвертации RAM в число: {e}. Значение было: '{ram_pct_raw}'")
            except Exception as e:
                logger.error(f"Непредвиденная ошибка в фоновом таске: {e}")
        await asyncio.sleep(30)

async def line_main():
    logger.info("Запуск процесса Polling...")
    asyncio.create_task(scheduled_tasks())
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(line_main())