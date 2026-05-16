#!/bin/bash

# 1. Сбор метрик RAM (вывод free в мегабайтах, переводим в гигабайты с округлением)
ram_total_mb=$(free -m | awk '/^Mem:/{print $2}')
ram_used_mb=$(free -m | awk '/^Mem:/{print $3}')
ram_total_gb=$(echo "scale=2; $ram_total_mb / 1024" | bc)
ram_used_gb=$(echo "scale=2; $ram_used_mb / 1024" | bc)
ram_pct=$(echo "scale=2; ($ram_used_mb * 100) / ram_total_mb" | bc)

# 2. Сбор метрик Диска (берем корневой раздел '/')
disk_total_gb=$(df -h / | awk 'NR==2 {print $2}' | sed 's/G//')
disk_free_gb=$(df -h / | awk 'NR==2 {print $4}' | sed 's/G//')

# 3. Сбор метрик CPU (средняя загрузка за последнюю 1 минуту)
cpu_load=$(cat /proc/loadavg | awk '{print $1}')

# 4. Формируем чистый JSON-файл
cat <<EOF > /opt/traffic_bot/vps_stat_bot/system_data.json
{
  "ram": {
    "total_gb": ${ram_total_gb:-0},
    "used_gb": ${ram_used_gb:-0},
    "pct": ${ram_pct:-0}
  },
  "disk": {
    "total_gb": "${disk_total_gb:-0}",
    "free_gb": "${disk_free_gb:-0}"
  },
  "cpu": {
    "load": "${cpu_load:-0}"
  }
}
EOF