# Используем легкий образ Python
FROM python:3.11-slim

# Устанавливаем рабочую директорию внутри контейнера
WORKDIR /app

# Устанавливаем библиотеки
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь код бота в контейнер
COPY . .

# ИНСТРУКЦИЯ: Указываем команду для запуска бота
CMD ["python", "bot.py"]