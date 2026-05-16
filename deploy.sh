#!/bin/bash

# --- НАСТРОЙКИ ПРОЕКТА ---
PROJECT_DIR="/opt/traffic_bot/vps_stat_bot"
CONTAINER_NAME="my_traffic_bot"
IMAGE_NAME="traffic_bot"

echo "🚀 Запуск процесса автоматического деплоя бота..."

# 1. Переходим в папку проекта
cd $PROJECT_DIR || { echo "❌ Ошибка: Папка $PROJECT_DIR не найдена!"; exit 1; }

# 2. Подтягиваем свежий код из GitHub
echo "📥 Получение обновлений из GitHub..."
git pull origin main

# 3. Проверяем, существует ли локальный файл .env (защита от забывчивости)
if [ ! -f ".env" ]; then
    echo "🚨 КРИТИЧЕСКАЯ ОШИБКА: Файл .env отсутствует в папке $PROJECT_DIR!"
    echo "Пожалуйста, создайте его вручную на сервере перед запуском."
    exit 1
fi

# 4. Автоматически выставляем права на исполнение для скрипта мониторинга хоста
echo "⚙️ Настройка прав для системного мониторинга..."
chmod +x system_stats.sh

# 5. Останавливаем и удаляем старый Docker-контейнер, если он существует
echo "🗑️ Удаление старого контейнера..."
docker rm -f $CONTAINER_NAME 2>/dev/null

# 6. Собираем новый Docker-образ с игнорированием кэша
echo "📦 Сборка нового Docker-образа (без кэша)..."
docker build --no-cache -t $IMAGE_NAME .

# 7. Запускаем обновленный контейнер с монтированием двух JSON-файлов
echo "▶️ Запуск нового контейнера..."
docker run -d \
  --name $CONTAINER_NAME \
  --network host \
  -v $PROJECT_DIR/vnstat_data.json:/app/vnstat_data.json \
  -v $PROJECT_DIR/system_data.json:/app/system_data.json \
  --restart unless-stopped \
  $IMAGE_NAME

echo "✅ Деплой успешно завершен! Бот запущен и готов к работе."
echo "Убедиться в отсутствии ошибок можно командой: docker logs $CONTAINER_NAME"