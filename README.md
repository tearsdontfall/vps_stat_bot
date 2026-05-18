# 🌐 VPS Monitor Bot

Компактный Telegram-бот на Aiogram 3 и Docker для круглосуточного мониторинга ресурсов и сетевого трафика VPS-сервера.

## Что делает программа
* Собирает сетевой трафик (RX/TX) за текущий месяц через `vnStat`.
* Обновляет метрики хоста: CPU Load, RAM (с учетом кэша) и свободный Диск.
* Отправляет алерты в Telegram, если оперативная память загружена более чем на 50%.
* Ограничивает доступ к командам всем пользователям, кроме администратора.

---

## Структура файлов
```text
vps_stat_bot/
├── bot.py                 # Код бота (Python)
├── system_stats.sh        # Скрипт сбора метрик хоста (Bash)
├── Dockerfile             # Сборка контейнера
├── docker-compose.yml     # Оркестрация Docker
├── deploy.sh              # Скрипт автоматического деплоя
└── .env                   # Файл конфигурации (создается вручную)
```

## Установка
```bash
### Шаг 0. Создайте tg-бота через Botfather, получите токен доступа

### Шаг 1. Инициализация Git-репозитория на VPS
Зайдите на сервер по SSH, создайте целевую папку проекта и инициализируйте в ней чистый Git-репозиторий:
```bash
mkdir -p /opt/traffic_bot/vps_stat_bot
cd /opt/traffic_bot/vps_stat_bot
git init
git checkout -b main
# Настройка связи с удаленным репозиторием
git remote add origin git remote add origin git@github.com:tearsdontfall/vps_stat_bot.git

# Выполните в той же папке проекта на сервере, чтобы изменения прав файлов (chmod) не блокировали деплой:
git config core.filemode false

#Создайте файл .env в корне проекта на сервере и добавьте конфигурацию:
BOT_TOKEN=ваш_токен_бота_из_BotFather
ADMIN_ID=ваш_telegram_id_числом
MONTHLY_LIMIT_GB=1000.0

# Скопируйте скрипт деплоя на локальную машину, откройте скрипт /.deploy.sh, поправьте переменные под себя и запускайте:
REMOTE_DIR="/opt/traffic_bot/vps_stat_bot"
CONTAINER_NAME="my_traffic_bot"
IMAGE_NAME="traffic_bot"
SSH_KEY_PATH="$HOME/.ssh/id_ed25519"
VPS_CREDS="my-server" ##сюда либо домен из ~/.ssh/config, либо ip+port сервера
/.deploy.sh

# После удачного деплоя советую проверить контейнер:
docker ps
# И логи на предмет неисправностей
docker logs my_traffic_bot
```

