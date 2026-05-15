FROM python:3.10-slim

WORKDIR /app

# Копируем файлы проекта
COPY bot.py .
COPY .env .

# Устанавливаем только библиотеку для работы с Telegram-ботом
RUN pip install --no-cache-dir aiogram python-dotenv

CMD ["python", "bot.py"]