#!/bin/bash
cd /home/black/bot_laptop
# Перевіряємо наявність оновлень
git fetch origin main
LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse @{u})

if [ "$LOCAL" != "$REMOTE" ]; then
    echo "$(date): Оновлення знайдено. Завантажую..."
    git pull origin main
    # Оновлюємо залежності, якщо requirements.txt змінився
    ./venv/bin/pip install -r requirements.txt
    # Перезапускаємо бота
    systemctl --user restart laptop-bot.service
    echo "$(date): Бот оновлений та перезапущений."
else
    echo "$(date): Оновлень немає."
fi
