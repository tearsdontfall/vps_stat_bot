#!/bin/bash

# ==============================================================================
# НАСТРОЙКИ АВТОМАТИЗАЦИИ
# ==============================================================================
REMOTE_DIR="/opt/traffic_bot/vps_stat_bot"
CONTAINER_NAME="my_traffic_bot"
IMAGE_NAME="traffic_bot"
SSH_KEY_PATH="$HOME/.ssh/id_ed25519"
VPS_CREDS="my-server" ##сюда либо домен из ~/.ssh/config, либо ip+port сервера

# ==============================================================================
# ШАГ 0: АВТОМАТИЧЕСКАЯ НАСТРОЙКА SSH-АГЕНТА НА MAC
# ==============================================================================
if [ -z "$SSH_AUTH_SOCK" ]; then
   echo "🔑 [LOCAL] Запуск локального ssh-agent..."
   eval "$(ssh-agent -s)"
fi

ssh-add -l | grep -q "$SSH_KEY_PATH"
if [ $? -ne 0 ]; then
   echo "🔐 [LOCAL] Загрузка основного SSH-канала в оперативную память Mac..."
   ssh-add --apple-use-keychain "$SSH_KEY_PATH"
fi

echo "🛫 [LOCAL] Начало процесса деплоя с Вашего Mac..."

# ==============================================================================
# ШАГ 1: ПОДКЛЮЧЕНИЕ К VPS И ОБНОВЛЕНИЕ КОДА ИЗ GITHUB
# ==============================================================================
echo "🌐 [LOCAL] Подключение к VPS по SSH для очистки и обновления папки..."
ssh -A my-server << EOF
  echo "📥 [VPS] Переход в папку проекта..."
  cd $REMOTE_DIR || { mkdir -p $REMOTE_DIR && cd $REMOTE_DIR; }

  echo "🔄 [VPS] Получение обновлений из GitHub..."
  git pull origin main

  echo "⚙️ [VPS] Настройка прав для скрипта мониторинга хоста..."
  chmod +x system_stats.sh
EOF

# ==============================================================================
# ШАГ 2: КОПИРОВАНИЕ КОНФИГУРАЦИОННОГО ФАЙЛА .ENV
# ==============================================================================
echo "🔐 [LOCAL] Безопасное копирование файла .env на сервер..."
scp .env my-server:$REMOTE_DIR/.env

# ==============================================================================
# ШАГ 3: ЖЕСТКАЯ ОЧИСТКА И ПЕРЕЗАПУСК DOCKER (ИСПРАВЛЕННЫЙ ПОРЯДОК)
# ==============================================================================
echo "🐳 [LOCAL] Проверка структуры данных и запуск Docker на сервере..."
ssh -A my-server << EOF
  cd $REMOTE_DIR

  echo "🛑 [VPS] ШАГ 1: Принудительное удаление контейнера (чтобы освободить файлы)..."
  docker rm -f $CONTAINER_NAME 2>/dev/null

  echo "🧹 [VPS] ШАГ 2: Очистка ложных директорий и создание правильных файлов..."
  
  # Проверяем system_data.json
  if [ -d "system_data.json" ] || [ ! -f "system_data.json" ]; then
    echo "  -> Пересоздаем system_data.json как файл"
    rm -rf system_data.json
    echo "{}" > system_data.json
    chmod 666 system_data.json
  fi

  # Проверяем vnstat_data.json
  if [ -d "vnstat_data.json" ] || [ ! -f "vnstat_data.json" ]; then
    echo "  -> Пересоздаем vnstat_data.json как файл"
    rm -rf vnstat_data.json
    echo "{}" > vnstat_data.json
    chmod 666 vnstat_data.json
  fi

  echo "📦 [VPS] ШАГ 3: Сборка нового Docker-образа..."
  docker build --no-cache -t $IMAGE_NAME .

  echo "▶️ [VPS] ШАГ 4: Запуск контейнера со свежим монтированием..."
  docker run -d \
    --name $CONTAINER_NAME \
    --network host \
    -v $REMOTE_DIR/vnstat_data.json:/app/vnstat_data.json \
    -v $REMOTE_DIR/system_data.json:/app/system_data.json \
    --restart unless-stopped \
    $IMAGE_NAME

  echo "✅ [VPS] Контейнер успешно пересобран и запущен!"
EOF

echo "🎉 [LOCAL] Деплой полностью завершен! Ошибки директорий JSON устранены."