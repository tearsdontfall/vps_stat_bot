#!/bin/bash

# ==============================================================================
# НАСТРОЙКИ АВТОМАТИЗАЦИИ (ЗАМЕНИ IP НА СВОЙ)
# ==============================================================================
SERVER_IP="151.245.136.103:4719"
SERVER_USER="root"
REMOTE_DIR="/opt/traffic_bot/vps_stat_bot"
CONTAINER_NAME="my_traffic_bot"
IMAGE_NAME="traffic_bot"

echo "🛫 [LOCAL] Начало процесса деплоя с Вашего Mac..."

# 1. Отправляем свежий код в GitHub, чтобы сервер мог его забрать
echo "📤 [LOCAL] Отправка свежего кода в GitHub репозиторий..."
git add .
git commit -m "Автоматический деплой: обновление кода"
git push origin main

# 2. Копируем локальный файл .env с Mac на VPS в целевую папку
echo "🔐 [LOCAL] Безопасное копирование файла .env на сервер через SCP..."
scp .env $SERVER_USER@$SERVER_IP:$REMOTE_DIR/.env

# 3. Подключаемся к серверу по SSH и выполняем команды сборки Docker
echo "🌐 [LOCAL] Подключение к VPS по SSH для сборки проекта..."
ssh $SERVER_USER@$SERVER_IP << EOF
  echo "📥 [VPS] Переход в папку проекта и обновление кода из GitHub..."
  cd $REMOTE_DIR
  git fetch origin
  git reset --hard origin/main

  echo "⚙️ [VPS] Настройка прав для скрипта мониторинга хоста..."
  chmod +x system_stats.sh

  echo "🗑️ [VPS] Остановка и удаление старого контейнера..."
  docker rm -f $CONTAINER_NAME 2>/dev/null

  echo "📦 [VPS] Сборка нового Docker-образа без использования кэша..."
  docker build --no-cache -t $IMAGE_NAME .

  echo "▶️ [VPS] Запуск обновленного контейнера..."
  docker run -d \
    --name $CONTAINER_NAME \
    --network host \
    -v $REMOTE_DIR/vnstat_data.json:/app/vnstat_data.json \
    -v $REMOTE_DIR/system_data.json:/app/system_data.json \
    --restart unless-stopped \
    $IMAGE_NAME

  echo "✅ [VPS] Контейнер успешно пересобран и запущен на сервере!"
EOF

echo "🎉 [LOCAL] Деплой полностью завершен! Бот обновлен и готов к работе."