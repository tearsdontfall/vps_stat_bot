FROM python:3.10-slim

# Устанавливаем vnstat в систему контейнера
RUN apt-get update && apt-get install -y vnstat && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Копируем файлы проекта
COPY bot.py .
COPY .env .

# Устанавливаем необходимые Python-пакеты напрямую в систему
RUN pip install --no-cache-dir aiogram python-dotenv

# Запускаем скрипт
CMD ["python", "bot.py"]